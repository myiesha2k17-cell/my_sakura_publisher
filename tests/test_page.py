import pytest
from streamlit.testing.v1 import AppTest

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = str(ROOT / "pages" / "1_Shorts_Studio.py")
KEYS = ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY", "SHORTS_PASSWORD", "SHORTS_FAKE_PROVIDERS"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SHORTS_OUTPUT_DIR", str(tmp_path / "output"))


def unlocked(timeout=30):
    at = AppTest.from_file(PAGE, default_timeout=timeout)
    at.secrets["SHORTS_PASSWORD"] = "sakura"
    at.run()
    at.text_input(key="password").input("sakura").run()
    return at


def test_locked_without_password_secret():
    at = AppTest.from_file(PAGE).run()
    assert not at.exception
    assert any("Set SHORTS_PASSWORD" in m.value for m in list(at.info))
    assert len(at.selectbox) == 0


def test_wrong_password_stays_locked():
    at = AppTest.from_file(PAGE)
    at.secrets["SHORTS_PASSWORD"] = "sakura"
    at.run()
    at.text_input(key="password").input("nope").run()
    assert len(at.selectbox) == 0
    assert any("Wrong password" in e.value for e in at.error)


def test_missing_keys_disable_buttons():
    at = unlocked()
    assert not at.exception
    assert at.button(key="write").disabled
    assert any("ANTHROPIC_API_KEY" in i.value for i in at.info)


@pytest.mark.slow
def test_fake_flow(monkeypatch):
    monkeypatch.setenv("SHORTS_FAKE_PROVIDERS", "1")
    at = unlocked(timeout=240)
    at.selectbox(key="book").set_value("the_ledger").run()
    at.selectbox(key="format").set_value("trope_hook").run()
    at.button(key="write").click().run()
    assert not at.exception, at.exception
    assert not at.button(key="render_0").disabled
    at.button(key="render_0").click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert len(at.get("download_button")) == 1


def test_journal_app_untouched():
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
