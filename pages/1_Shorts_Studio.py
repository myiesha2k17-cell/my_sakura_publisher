"""Hanako Shorts Studio — turn a catalog book into a ready-to-post vertical short."""
import hmac
import logging
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from shorts.catalog import load_catalog
from shorts.formats import FORMATS, formats_for
import shorts.pipeline as pipeline
from shorts.providers import make_providers
from shorts.providers.base import ProviderError
from shorts.render import RenderError
from shorts.script import ScriptError
from shorts.settings import CapReached, DailyCap, Settings

log = logging.getLogger("shorts_studio")
FRIENDLY = "Something went wrong. Please try again; if it keeps happening, check the app logs."
from shorts.voices import load_voices

st.set_page_config(page_title="Hanako Shorts Studio", page_icon="🌸", layout="centered")


def _secrets() -> dict:
    try:
        return dict(st.secrets)
    except Exception:  # no secrets file configured
        return {}


settings = Settings.from_sources(os.environ, _secrets())
st.title("🌸 Hanako Shorts Studio")

# ---- 1. Password gate -------------------------------------------------------
if not settings.password:
    st.info("Set SHORTS_PASSWORD in the app's secrets to use this page.")
    st.stop()
if not st.session_state.get("unlocked"):
    pw = st.text_input("Password", type="password", key="password")
    if pw and hmac.compare_digest(pw, settings.password):
        st.session_state.unlocked = True
        st.rerun()
    elif pw:
        st.error("Wrong password.")
    st.stop()

# ---- 2. Setup ---------------------------------------------------------------
catalog = load_catalog()
voices = load_voices()
llm, tts, images = make_providers(settings)
fake_mode = os.environ.get("SHORTS_FAKE_PROVIDERS") == "1"
cap = DailyCap(Path(settings.output_dir) / ".daily_cap.json", settings.daily_cap)
missing_script = [] if fake_mode else settings.missing_for_script()
if fake_mode:
    st.warning("Demo mode: offline stand-ins, not real voice or scripts.")
if missing_script:
    st.info(f"To write scripts, add {', '.join(missing_script)} to the app's secrets.")
if not settings.openai_key and not fake_mode:
    st.caption("No OPENAI_API_KEY: scene images will be made from the book cover.")

# ---- 3. Choose --------------------------------------------------------------
book_id = st.selectbox("Book", list(catalog), key="book",
                       format_func=lambda b: f"{catalog[b].title} — {catalog[b].author}")
book = catalog[book_id]
book_blockers = pipeline.render_blockers(settings, voices[book.voice], fake_mode)
if book_blockers:
    st.info("To render videos for this book: " + "; ".join(book_blockers) + ".")
options = [f.id for f in formats_for(book.book_type)]
format_id = st.selectbox("Format", options, key="format", format_func=lambda f: FORMATS[f].name)
col1, col2 = st.columns(2)
n = col1.number_input("Variants", min_value=1, max_value=3, value=1, key="variants")
skip_review = col2.checkbox("Skip review (render straight away)", key="skip_review")
extra = st.text_area("Extra direction (optional)", key="extra",
                     placeholder="e.g. lean into the mother–daughter angle")
st.caption(f"Shorts left today: {cap.remaining(date.today())} of {settings.daily_cap}")


def _show_error(e: Exception) -> None:
    st.error(str(e) or e.__class__.__name__)


def _render(index: int, script) -> None:
    def work():
        with st.status("Rendering…", expanded=True) as status:
            st.write("Voice, images, captions and video — this takes a few minutes.")
            result = pipeline.stage2_render(script, tts, images, catalog, voices, settings)
            status.update(label="Done", state="complete")
        return result

    try:
        st.session_state.setdefault("results", {})[index] = pipeline.run_counted(cap, date.today(), work)
    except (ScriptError, ProviderError, RenderError, CapReached) as e:
        _show_error(e)
    except Exception:  # never show a traceback (or internal details) on the page
        log.exception("Render failed")
        st.error(FRIENDLY)


# ---- 4. Write scripts -------------------------------------------------------
if st.button("Write scripts", key="write", type="primary", disabled=bool(missing_script)):
    try:
        with st.spinner("Writing in the author's voice…"):
            st.session_state.scripts = pipeline.stage1_scripts(book_id, format_id, int(n), extra, llm, catalog,
                                                               voices)
        st.session_state.results = {}
        st.session_state.gen = st.session_state.get("gen", 0) + 1  # fresh widget keys for the new batch
        if skip_review and not book_blockers:
            for i, (script, _) in enumerate(st.session_state.scripts):
                _render(i, script)
    except (ScriptError, ProviderError) as e:
        _show_error(e)
    except Exception:
        log.exception("Script writing failed")
        st.error(FRIENDLY)

# ---- 5. Review, edit, render ------------------------------------------------
gen = st.session_state.get("gen", 0)
for i, (script, report) in enumerate(st.session_state.get("scripts", [])):
    blockers = pipeline.render_blockers(settings, voices[catalog[script.book_id].voice], fake_mode)
    with st.expander(f"Variant {i + 1}: {script.hook}", expanded=True):
        for flag in report.flags:
            st.warning(flag)
        if report.revised is not None:
            st.caption("The fact check revised this script; the flags above describe what it fixed.")
        table = pd.DataFrame([s.model_dump() for s in script.scenes])
        edited = st.data_editor(table, key=f"scenes_{gen}_{i}", width="stretch", hide_index=True,
                                disabled=["role", "seconds"])
        script.scenes = pipeline.scenes_from_rows(edited.to_dict("records"))
        script.post.tiktok_caption = st.text_area("TikTok caption", script.post.tiktok_caption, key=f"tt_{gen}_{i}")
        script.post.instagram_caption = st.text_area("Instagram caption", script.post.instagram_caption, key=f"ig_{gen}_{i}")
        script.post.youtube_title = st.text_input("YouTube title", script.post.youtube_title, key=f"yt_{gen}_{i}",
                                                  max_chars=100)
        script.post.youtube_description = st.text_area("YouTube description", script.post.youtube_description,
                                                       key=f"ytd_{gen}_{i}")
        out_of_cap = cap.remaining(date.today()) == 0
        if st.button("Approve & Render", key=f"render_{i}", disabled=bool(blockers) or out_of_cap):
            _render(i, script)
        result = st.session_state.get("results", {}).get(i)
        if result is not None:
            for w in result.warnings:
                st.info(w)
            st.video(str(result.video))
            st.download_button("Download video + post text (zip)", Path(result.zip).read_bytes(),
                               file_name=Path(result.zip).name, mime="application/zip", key=f"dl_{gen}_{i}")
            st.markdown("**Post text** — tap a block's copy icon:")
            st.code(result.post_md, language="markdown")
