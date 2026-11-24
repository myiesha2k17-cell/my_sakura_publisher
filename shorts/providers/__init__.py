"""Provider construction from settings."""
from __future__ import annotations

import os

from shorts.settings import Settings


def make_providers(settings: Settings):
    """Return (llm, tts, images). A provider is None when its key is missing.

    SHORTS_FAKE_PROVIDERS=1 swaps in offline fakes — for tests and demos only, never in production.
    """
    if os.environ.get("SHORTS_FAKE_PROVIDERS") == "1":
        from shorts.providers.fakes import DemoLLM, FakeImageGen, FakeTTS
        return DemoLLM(), FakeTTS(), FakeImageGen()

    from shorts.providers.anthropic_llm import AnthropicLLM
    from shorts.providers.cover_only import CoverOnlyImages
    from shorts.providers.elevenlabs_tts import ElevenLabsTTS
    from shorts.providers.openai_images import OpenAIImages

    llm = AnthropicLLM(settings.anthropic_key, settings.claude_model) if settings.anthropic_key else None
    tts = ElevenLabsTTS(settings.elevenlabs_key) if settings.elevenlabs_key else None
    images = OpenAIImages(settings.openai_key) if settings.openai_key else CoverOnlyImages()
    return llm, tts, images
