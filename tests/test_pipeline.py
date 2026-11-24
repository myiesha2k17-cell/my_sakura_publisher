import zipfile

import pytest

from shorts.catalog import load_catalog
from shorts.models import GuardrailReview, PostText, Scene, ScriptDraft
from shorts.pipeline import MAX_AUDIO, stage1_scripts, stage2_render
from shorts.providers.fakes import FakeImageGen, FakeLLM, FakeTTS
from shorts.render import probe
from shorts.script import ScriptError
from shorts.settings import Settings
from shorts.voices import load_voices

REMINDER = 'Reminder: turn on the platform\'s "AI-generated content" label (AI voice/images used).'


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def voices():
    return load_voices()


@pytest.fixture
def settings(tmp_path):
    return Settings.from_sources({"SHORTS_OUTPUT_DIR": str(tmp_path / "output")}, None)


def make_draft(roles, words_per_scene=4):
    scenes = [Scene(role=r, narration=" ".join(f"w{i}x{j}" for j in range(words_per_scene)),
                    on_screen_text=f"Beat {i}", image_prompt=f"prompt {i}", seconds=5)
              for i, r in enumerate(roles)]
    return ScriptDraft(hook="POV: a ledger", scenes=scenes, cta="Link in bio.",
                       post=PostText(tiktok_caption="tt", instagram_caption="ig", youtube_title="The Ledger",
                                     youtube_description="yt", hashtags=["#Orisha"]))


def ledger_script(catalog, voices, words_per_scene=4):
    roles = ["hook", "trope", "trope", "trope", "cover_reveal", "cta"]
    llm = FakeLLM([make_draft(roles, words_per_scene), GuardrailReview()])
    [(script, report)] = stage1_scripts("the_ledger", "trope_hook", 1, "", llm, catalog, voices)
    return script, report


def test_end_to_end_fake(tmp_path, catalog, voices, settings):
    script, report = ledger_script(catalog, voices)
    assert report.ok
    result = stage2_render(script, FakeTTS(), FakeImageGen(), catalog, voices, settings, music_dir=tmp_path / "none")
    names = zipfile.ZipFile(result.zip).namelist()
    assert {"short.mp4", "post.md", "script.json"} <= set(names)
    assert any(n.startswith("images/") for n in names)
    info = probe(result.video)
    assert (info["width"], info["height"]) == (1080, 1920) and info["duration"] < 60
    assert "https://a.co/d/0dXjLJ2d" in result.post_md
    assert result.post_md.rstrip().endswith(REMINDER)
    assert "## TikTok" in result.post_md and "## YouTube Shorts" in result.post_md


def test_too_long_errors(tmp_path, catalog, voices, settings):
    script, _ = ledger_script(catalog, voices, words_per_scene=7)  # 42 words
    with pytest.raises(ScriptError, match="too long"):
        stage2_render(script, FakeTTS(words_per_sec=0.5), FakeImageGen(), catalog, voices, settings,
                      music_dir=tmp_path / "none")


def test_slightly_long_is_sped_up(tmp_path, catalog, voices, settings):
    script, _ = ledger_script(catalog, voices, words_per_scene=5)  # 30 words -> 60 s at 0.5 w/s
    result = stage2_render(script, FakeTTS(words_per_sec=0.5), FakeImageGen(), catalog, voices, settings,
                           music_dir=tmp_path / "none")
    assert result.voice_duration <= MAX_AUDIO + 0.5
    assert probe(result.video)["duration"] < 60


def test_no_music_warning(tmp_path, catalog, voices, settings):
    script, _ = ledger_script(catalog, voices)
    result = stage2_render(script, FakeTTS(), FakeImageGen(), catalog, voices, settings, music_dir=tmp_path / "none")
    assert "No music in assets/music — rendered voice only." in result.warnings


def test_flip_through_uses_journal_pages(tmp_path, catalog, voices, settings):
    roles = ["page", "page", "page", "page", "page", "cta"]
    llm = FakeLLM([make_draft(roles), GuardrailReview()])
    [(script, _)] = stage1_scripts("sakura_calm", "flip_through", 1, "", llm, catalog, voices)
    images = FakeImageGen()
    result = stage2_render(script, FakeTTS(), images, catalog, voices, settings, music_dir=tmp_path / "none")
    assert images.calls == 0
    pngs = [n for n in zipfile.ZipFile(result.zip).namelist() if n.startswith("images/") and n.endswith(".png")]
    assert len(pngs) == 5


def test_rerender_uses_cache(tmp_path, catalog, voices, settings):
    script, _ = ledger_script(catalog, voices)
    tts, images = FakeTTS(), FakeImageGen()
    first = stage2_render(script, tts, images, catalog, voices, settings, music_dir=tmp_path / "none")
    stage2_render(script, tts, images, catalog, voices, settings, music_dir=tmp_path / "none", run_dir=first.run_dir)
    assert tts.calls == 1
    assert images.calls == 5  # 6 scenes, the cover_reveal scene uses the real cover
