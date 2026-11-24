import base64
import io
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

from shorts.catalog import load_catalog
from shorts.models import PostText
from shorts.providers import elevenlabs_tts, openai_images
from shorts.providers.anthropic_llm import AnthropicLLM
from shorts.providers.base import ProviderError, Refusal
from shorts.providers.cover_only import CoverOnlyImages
from shorts.providers.elevenlabs_tts import ElevenLabsTTS
from shorts.providers.openai_images import OpenAIImages
from shorts.settings import Settings
from shorts.providers import make_providers


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def _mp3_b64(seconds=2.0):
    out = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(seconds),
                          "-f", "mp3", "-"], capture_output=True, check=True).stdout
    return base64.b64encode(out).decode()


def test_elevenlabs_word_timings(tmp_path, monkeypatch):
    text = "Not superstition. Bookkeeping."
    starts = [0.1 * i for i in range(len(text))]
    payload = {"audio_base64": _mp3_b64(), "alignment": {
        "characters": list(text), "character_start_times_seconds": starts,
        "character_end_times_seconds": [s + 0.08 for s in starts]}}
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers)
        return FakeResponse(200, payload)

    monkeypatch.setattr(elevenlabs_tts.requests, "post", fake_post)
    result = ElevenLabsTTS("k-secret").synthesize(text, "voice123", tmp_path / "v.mp3")
    assert seen["url"].endswith("/v1/text-to-speech/voice123/with-timestamps")
    assert seen["headers"]["xi-api-key"] == "k-secret"
    assert [w.word for w in result.words] == ["Not", "superstition.", "Bookkeeping."]
    assert [round(w.start, 2) for w in result.words] == [0.0, 0.4, 1.8]
    assert result.audio_path.exists() and abs(result.duration - 2.0) < 0.2


def test_elevenlabs_http_error(tmp_path, monkeypatch):
    monkeypatch.setattr(elevenlabs_tts.requests, "post", lambda *a, **k: FakeResponse(401, {"detail": "bad key"}))
    with pytest.raises(ProviderError) as e:
        ElevenLabsTTS("k-secret").synthesize("hi", "v", tmp_path / "v.mp3")
    assert "ElevenLabs" in str(e.value) and "401" in str(e.value)
    assert "k-secret" not in str(e.value)


def test_openai_images_writes_png(tmp_path, monkeypatch):
    buf = io.BytesIO()
    Image.new("RGB", (1024, 1536), "red").save(buf, format="PNG")
    payload = {"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode()}]}
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(json=json)
        return FakeResponse(200, payload)

    monkeypatch.setattr(openai_images.requests, "post", fake_post)
    out = OpenAIImages("ok").generate("a dusk crossroads", tmp_path / "i.png", load_catalog()["the_ledger"])
    assert Image.open(out).size == (1024, 1536)
    assert seen["json"]["size"] == "1024x1536"


def test_cover_only_distinct(tmp_path):
    gen = CoverOnlyImages()
    book = load_catalog()["the_ledger"]
    outs = [gen.generate("ignored", tmp_path / f"{i}.png", book) for i in range(3)]
    images = [Image.open(o) for o in outs]
    assert all(im.width >= 1024 and im.height >= 1536 for im in images)
    assert len({im.tobytes() for im in images}) == 3


def test_cover_only_without_cover(tmp_path):
    book = load_catalog()["sakura_calm"]
    out = CoverOnlyImages().generate("x", tmp_path / "a.png", book)
    assert Image.open(out).size == (1024, 1536)


def _stub_client(response, seen):
    def parse(**kwargs):
        seen.update(kwargs)
        return response
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))


def test_anthropic_parse_uses_model_and_fallbacks():
    post = PostText(tiktok_caption="a", instagram_caption="b", youtube_title="c", youtube_description="d")
    seen = {}
    client = _stub_client(SimpleNamespace(stop_reason="end_turn", parsed_output=post, stop_details=None), seen)
    out = AnthropicLLM("key", "claude-opus-5-5", client=client).parse("sys", "user", PostText)
    assert out == post
    assert seen["model"] == "claude-opus-5-5" and seen["output_format"] is PostText
    assert seen["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen["betas"]
    assert seen["system"] == "sys" and seen["messages"][0]["content"] == "user"


def test_anthropic_refusal():
    client = _stub_client(SimpleNamespace(stop_reason="refusal", parsed_output=None,
                                          stop_details=SimpleNamespace(category="general_harms")), {})
    with pytest.raises(Refusal):
        AnthropicLLM("key", "claude-opus-5-5", client=client).parse("s", "u", PostText)


def test_make_providers_without_keys(monkeypatch):
    monkeypatch.delenv("SHORTS_FAKE_PROVIDERS", raising=False)
    llm, tts, images = make_providers(Settings.from_sources({}, None))
    assert llm is None and tts is None and isinstance(images, CoverOnlyImages)


def test_make_providers_with_keys(monkeypatch):
    monkeypatch.delenv("SHORTS_FAKE_PROVIDERS", raising=False)
    llm, tts, images = make_providers(Settings.from_sources(
        {"ANTHROPIC_API_KEY": "a", "ELEVENLABS_API_KEY": "e", "OPENAI_API_KEY": "o"}, None))
    assert isinstance(llm, AnthropicLLM) and isinstance(tts, ElevenLabsTTS) and isinstance(images, OpenAIImages)
