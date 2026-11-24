import pytest
from pydantic import ValidationError

from shorts.catalog import load_catalog
from shorts.formats import FORMATS
from shorts.models import PostText, Scene, ScriptDraft, GuardrailReview
from shorts.providers.base import Refusal
from shorts.providers.fakes import FakeLLM
from shorts.script import ScriptError, build_prompt, check_script, merge_hashtags, write_scripts
from shorts.voices import load_voices


@pytest.fixture
def ledger():
    return load_catalog()["the_ledger"]


@pytest.fixture
def ren():
    return load_voices()["ren_hawthorne"]


def draft(hook="POV: you inherit a ledger of debts to the gods", seconds=5.0, on_screen="Not superstition.", n_scenes=6):
    scenes = [Scene(role="beat", narration=f"Line {i}.", on_screen_text=on_screen, image_prompt="a dusk crossroads",
                    seconds=seconds) for i in range(n_scenes)]
    post = PostText(tiktok_caption="cap", instagram_caption="cap", youtube_title="The Ledger",
                    youtube_description="desc", hashtags=["#BookTok", "#Orisha"])
    return ScriptDraft(hook=hook, scenes=scenes, cta="Link in bio.", post=post)


def a_validation_error():
    try:
        Scene()
    except ValidationError as e:
        return e


def test_prompt_contains_only_catalog_facts(ledger, ren):
    system, user = build_prompt(ledger, ren, FORMATS["trope_hook"])
    assert ledger.blurb in user
    for q in ledger.quotes:
        assert q in user
    assert "Never mention" in user
    for item in ledger.do_not_say:
        assert item in user
    assert "Hanako Design & Media" in user and "Link in bio" in user
    assert ren.tone in system
    for w in ren.avoid_words:
        assert w in system


def test_write_scripts_n(ledger, ren):
    llm = FakeLLM([draft(hook="Hook one"), draft(hook="Hook two")])
    scripts = write_scripts(llm, ledger, ren, FORMATS["trope_hook"], n=2)
    assert len(scripts) == 2 and len(llm.calls) == 2
    assert all(s.book_id == "the_ledger" and s.format_id == "trope_hook" for s in scripts)
    assert "Hook one" in llm.calls[1][1] and "different angle" in llm.calls[1][1]


def test_validation_retry_then_error(ledger, ren):
    llm = FakeLLM([a_validation_error(), a_validation_error()])
    with pytest.raises(ScriptError, match="could not produce a valid script"):
        write_scripts(llm, ledger, ren, FORMATS["trope_hook"])
    assert len(llm.calls) == 2


def test_validation_retry_then_success(ledger, ren):
    llm = FakeLLM([a_validation_error(), draft()])
    assert len(write_scripts(llm, ledger, ren, FORMATS["trope_hook"])) == 1


def test_refusal_is_script_error(ledger, ren):
    llm = FakeLLM([Refusal("policy")])
    with pytest.raises(ScriptError, match="declined"):
        write_scripts(llm, ledger, ren, FORMATS["trope_hook"])


def test_guardrail_flags_unlisted_quote(ledger, ren):
    llm = FakeLLM([draft(on_screen='"Not superstition. Bookkeeping."')])
    script = write_scripts(llm, ledger, ren, FORMATS["read_this_line"])[0]
    script.scenes[1].on_screen_text = "“Every debt gets paid in blood.”"
    review_llm = FakeLLM([GuardrailReview(flags=[], revised=None)])
    report = check_script(review_llm, script, ledger, ren)
    assert not report.ok
    assert any("Every debt gets paid in blood." in f for f in report.flags)
    assert not any("Bookkeeping" in f for f in report.flags)


def test_guardrail_clean(ledger, ren):
    script = write_scripts(FakeLLM([draft()]), ledger, ren, FORMATS["trope_hook"])[0]
    report = check_script(FakeLLM([GuardrailReview(flags=[], revised=None)]), script, ledger, ren)
    assert report.ok and report.flags == []


def test_hashtags_no_booktok_for_journals(ren):
    journal = load_catalog()["sakura_calm"]
    hanako = load_voices()["hanako"]
    script = write_scripts(FakeLLM([draft()]), journal, hanako, FORMATS["prompt_of_the_day"])[0]
    tags = merge_hashtags(script, journal, hanako)
    assert not any("booktok" in t.lower() for t in tags)


def test_hashtags_deduped_max_8(ledger, ren):
    script = write_scripts(FakeLLM([draft()]), ledger, ren, FORMATS["trope_hook"])[0]
    script.post.hashtags = ["#BookTok", "booktok", "#Orisha", "#A", "#B", "#C", "#D", "#E", "#F"]
    tags = merge_hashtags(script, ledger, ren)
    assert len(tags) <= 8
    assert len({t.lower() for t in tags}) == len(tags)
    assert all(t.startswith("#") for t in tags)
    assert "#HanakoDesignAndMedia" in tags


def test_total_seconds_within_format(ledger, ren):
    script = write_scripts(FakeLLM([draft(seconds=20.0)]), ledger, ren, FORMATS["trope_hook"])[0]
    lo, hi = FORMATS["trope_hook"].target_seconds
    assert lo <= sum(s.seconds for s in script.scenes) <= hi
