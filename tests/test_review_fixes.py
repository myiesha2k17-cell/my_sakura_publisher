"""Regression tests for the whole-branch review findings."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from shorts.catalog import load_catalog
from shorts.models import GuardrailReview, PostText, Scene, ScriptDraft
from shorts.pipeline import _scene_times, stage1_scripts, stage2_render
from shorts.providers.anthropic_llm import AnthropicLLM
from shorts.providers.base import Refusal, TTSResult
from shorts.providers.fakes import FakeImageGen, FakeLLM, FakeTTS
from shorts.settings import CapReached, DailyCap, Settings
from shorts.voices import load_voices

ROOT = Path(__file__).resolve().parent.parent
PAGE = str(ROOT / "pages" / "1_Shorts_Studio.py")


# --- Finding 1: a new batch must not inherit the previous batch's widget text --------------
def test_new_batch_does_not_inherit_previous_text(monkeypatch, tmp_path):
    for k in ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY", "SHORTS_PASSWORD"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SHORTS_FAKE_PROVIDERS", "1")
    monkeypatch.setenv("SHORTS_OUTPUT_DIR", str(tmp_path))
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.secrets["SHORTS_PASSWORD"] = "sakura"
    at.run()
    at.text_input(key="password").input("sakura").run()
    at.selectbox(key="book").set_value("the_ledger").run()
    at.button(key="write").click().run()
    at.selectbox(key="book").set_value("the_ones_nobody_came_for").run()
    at.button(key="write").click().run()
    captions = [t.value for t in at.text_area if t.label == "TikTok caption"]
    assert captions and "The Ones Nobody Came For" in captions[0]


# --- Finding 2: no render without an ElevenLabs voice id ---------------------------------
def test_render_blocked_without_voice_id():
    from shorts.pipeline import render_blockers
    settings = Settings.from_sources({"ELEVENLABS_API_KEY": "e"}, None)
    voice = load_voices()["ren_hawthorne"].model_copy(update={"elevenlabs_voice_id": ""})
    blockers = render_blockers(settings, voice, fake_mode=False)
    assert any("elevenlabs_voice_id" in b and "ren_hawthorne" in b for b in blockers)
    ok_voice = voice.model_copy(update={"elevenlabs_voice_id": "abc"})
    assert render_blockers(settings, ok_voice, fake_mode=False) == []
    assert render_blockers(Settings.from_sources({}, None), voice, fake_mode=True) == []


# --- Finding 3: the daily cap is only spent on successful renders ------------------------
def test_cap_not_spent_on_failure(tmp_path):
    from shorts.pipeline import run_counted
    cap = DailyCap(tmp_path / "cap.json", limit=2)
    today = date(2026, 11, 24)

    def boom():
        raise RuntimeError("render failed")

    with pytest.raises(RuntimeError):
        run_counted(cap, today, boom)
    assert cap.remaining(today) == 2
    assert run_counted(cap, today, lambda: "ok") == "ok"
    assert cap.remaining(today) == 1


def test_cap_checked_before_running(tmp_path):
    from shorts.pipeline import run_counted
    cap = DailyCap(tmp_path / "cap.json", limit=1)
    today = date(2026, 11, 24)
    run_counted(cap, today, lambda: None)
    called = []
    with pytest.raises(CapReached):
        run_counted(cap, today, lambda: called.append(1))
    assert called == []


# --- Finding 4: cleared data_editor cells and unexpected errors --------------------------
def test_scenes_from_rows_coerces_blanks():
    from shorts.pipeline import scenes_from_rows
    scenes = scenes_from_rows([{"role": "hook", "narration": None, "on_screen_text": None,
                                "image_prompt": None, "seconds": None}])
    assert scenes[0].narration == "" and scenes[0].on_screen_text == "" and scenes[0].seconds == 0.0


def test_unexpected_error_shows_friendly_message(monkeypatch, tmp_path):
    for k in ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY", "SHORTS_PASSWORD"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SHORTS_FAKE_PROVIDERS", "1")
    monkeypatch.setenv("SHORTS_OUTPUT_DIR", str(tmp_path))
    import shorts.pipeline

    def explode(*a, **k):
        raise RuntimeError("internal-detail-xyz")

    monkeypatch.setattr(shorts.pipeline, "stage2_render", explode)
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.secrets["SHORTS_PASSWORD"] = "sakura"
    at.run()
    at.text_input(key="password").input("sakura").run()
    at.button(key="write").click().run()
    render = next(b for b in at.button if b.label == "Approve & Render")
    render.click().run()
    assert not at.exception
    errors = [e.value for e in at.error]
    assert errors and "internal-detail-xyz" not in " ".join(errors)
    assert DailyCap(tmp_path / ".daily_cap.json", 10).remaining(date.today()) == 10


# --- Finding 5: a refusal must be reported as a refusal, without a paid retry ------------
def _create_stub(response, calls):
    def create(**kwargs):
        calls.append(kwargs)
        return response
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))


def test_refusal_with_plain_text_is_refusal():
    calls = []
    response = SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(category="general_harms"),
                               content=[SimpleNamespace(type="text", text="I can't help with that.")])
    with pytest.raises(Refusal):
        AnthropicLLM("k", "claude-opus-5-5", client=_create_stub(response, calls)).parse("s", "u", PostText)
    assert len(calls) == 1
    assert calls[0]["output_config"]["format"]["type"] == "json_schema"
    assert calls[0]["fallbacks"] == "default"


def test_valid_json_is_parsed():
    post = PostText(tiktok_caption="a", instagram_caption="b", youtube_title="c", youtube_description="d")
    response = SimpleNamespace(stop_reason="end_turn", stop_details=None,
                               content=[SimpleNamespace(type="text", text=post.model_dump_json())])
    assert AnthropicLLM("k", "m", client=_create_stub(response, [])).parse("s", "u", PostText) == post


# --- Finding 6: a silent scene keeps its own time and does not steal from its neighbour --
def _script(word_counts, silent_seconds=2.0):
    scenes = [Scene(role="beat", narration=" ".join(["w"] * c), on_screen_text="t", image_prompt=f"p{i}",
                    seconds=silent_seconds if c == 0 else 2.0) for i, c in enumerate(word_counts)]
    post = PostText(tiktok_caption="a", instagram_caption="b", youtube_title="c", youtube_description="d")
    return ScriptDraft(hook="h", scenes=scenes, cta="c", post=post)


def test_silent_scene_gets_its_own_time(tmp_path):
    script = _script([4, 4, 0, 4], silent_seconds=2.0)
    voice = FakeTTS(words_per_sec=2.0).synthesize(" ".join(["w"] * 12), "v", tmp_path / "v.m4a")
    from shorts.pipeline import _insert_silences
    spoken = _insert_silences(script, voice, tmp_path)
    durations = _scene_times(script, spoken)
    assert durations[1] >= 1.5          # scene 2 keeps its spoken time
    assert 1.8 <= durations[2] <= 2.3   # silent scene gets ~its own 2 s
    assert spoken.duration >= voice.duration + 1.9


# --- Finding 7: voice and image caches survive a fresh run directory ---------------------
def test_cache_reused_across_runs(tmp_path):
    catalog, voices = load_catalog(), load_voices()
    roles = ["hook", "trope", "trope", "trope", "cover_reveal", "cta"]
    scenes = [Scene(role=r, narration=f"line {i} words here", on_screen_text="t", image_prompt=f"p{i}", seconds=5)
              for i, r in enumerate(roles)]
    draft = ScriptDraft(hook="h", scenes=scenes, cta="c", post=PostText(
        tiktok_caption="a", instagram_caption="b", youtube_title="c", youtube_description="d"))
    [(script, _)] = stage1_scripts("the_ledger", "trope_hook", 1, "", FakeLLM([draft, GuardrailReview()]),
                                   catalog, voices)
    settings = Settings.from_sources({"SHORTS_OUTPUT_DIR": str(tmp_path / "out")}, None)
    tts, images = FakeTTS(), FakeImageGen()
    a = stage2_render(script, tts, images, catalog, voices, settings, music_dir=tmp_path / "none")
    b = stage2_render(script, tts, images, catalog, voices, settings, music_dir=tmp_path / "none",
                      run_dir=tmp_path / "out" / "second-run")
    assert a.run_dir != b.run_dir
    assert tts.calls == 1 and images.calls == 5
