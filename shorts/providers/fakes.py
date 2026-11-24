"""Offline stand-ins for the real providers (tests and SHORTS_FAKE_PROVIDERS mode)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image
from pydantic import BaseModel

from shorts.models import Book, WordTiming
from shorts.providers.base import TTSResult


class FakeLLM:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, type]] = []

    def parse(self, system, user, schema):
        self.calls.append((system, user, schema))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response) and not isinstance(response, BaseModel):
            return response(system, user, schema)
        return response


class FakeTTS:
    def __init__(self, words_per_sec: float = 2.5):
        self.words_per_sec = words_per_sec
        self.calls = 0

    def synthesize(self, text: str, voice_id: str, out_path: Path) -> TTSResult:
        self.calls += 1
        words = text.split()
        step = 1.0 / self.words_per_sec
        duration = max(len(words), 1) * step
        out_path = Path(out_path).with_suffix(".m4a")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", f"{duration:.3f}", "-c:a", "aac", str(out_path)],
            check=True,
        )
        timings = [WordTiming(word=w, start=i * step, end=(i + 1) * step - 0.02) for i, w in enumerate(words)]
        return TTSResult(audio_path=out_path, words=timings, duration=duration)


class FakeImageGen:
    def __init__(self, color: str = "#2B2560"):
        self.color = color
        self.calls = 0

    def generate(self, prompt: str, out_path: Path, book: Book) -> Path:
        self.calls += 1
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1024, 1536), self.color).save(out_path)
        return out_path


class DemoLLM:
    """Offline script writer for SHORTS_FAKE_PROVIDERS demos: builds a plausible script from the prompt itself."""

    def parse(self, system, user, schema):
        from shorts.models import GuardrailReview, PostText, Scene, ScriptDraft

        if schema is GuardrailReview:
            return GuardrailReview()
        beats_line = next((l for l in user.splitlines() if l.startswith("Scenes, in order, one per beat:")), "")
        beats = [b.strip() for b in beats_line.split(":", 1)[-1].split(",") if b.strip()] or ["hook", "cta"]
        title = next((l.split(":", 1)[1].strip() for l in user.splitlines() if l.startswith("Book:")), "this book")
        scenes = [
            Scene(role=beat, narration=f"Demo line {i + 1} for {title}.", on_screen_text=f"{beat.replace('_', ' ')}",
                  image_prompt=f"moody scene {i + 1}", seconds=4.0)
            for i, beat in enumerate(beats)
        ]
        post = PostText(tiktok_caption=f"Demo caption for {title}", instagram_caption=f"Demo caption for {title}",
                        youtube_title=f"{title} (demo)", youtube_description="Demo description.")
        return ScriptDraft(hook=f"Demo hook for {title}", scenes=scenes, cta="Link in bio.", post=post)
