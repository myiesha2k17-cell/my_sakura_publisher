"""Interfaces for the external services the pipeline uses."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from shorts.models import Book, WordTiming

T = TypeVar("T", bound=BaseModel)


class Refusal(Exception):
    """The model declined the request."""


class ProviderError(Exception):
    """An external service failed. Message must never contain secrets."""


@dataclass
class TTSResult:
    audio_path: Path
    words: list[WordTiming]
    duration: float


class LLM(Protocol):
    def parse(self, system: str, user: str, schema: type[T]) -> T: ...


class TTS(Protocol):
    def synthesize(self, text: str, voice_id: str, out_path: Path) -> TTSResult: ...


class ImageGen(Protocol):
    def generate(self, prompt: str, out_path: Path, book: Book) -> Path: ...
