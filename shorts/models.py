"""Data models shared across the Shorts Studio engine."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BookType = Literal["fiction", "nonfiction", "devotional", "journal", "coloring"]


class Book(BaseModel):
    id: str
    title: str
    subtitle: str = ""
    series: str = ""
    author: str
    voice: str
    book_type: BookType
    amazon_url: str = ""
    blurb: str
    tropes: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    do_not_say: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    cover: str = ""
    page_images: list[str] = Field(default_factory=list)
    source_pdf: str = ""


class VoiceProfile(BaseModel):
    id: str
    display_name: str
    persona: str
    tone: str
    use_words: list[str] = Field(default_factory=list)
    avoid_words: list[str] = Field(default_factory=list)
    signature_phrases: list[str] = Field(default_factory=list)
    sign_off: str = ""
    elevenlabs_voice_id: str = ""
    palette: list[str] = Field(default_factory=list)
    font: str = "DejaVuSans-Bold"
    music_mood: str = ""
    default_hashtags: list[str] = Field(default_factory=list)


class WordTiming(BaseModel):
    word: str
    start: float
    end: float


class Format(BaseModel):
    id: str
    name: str
    book_types: list[BookType]
    beats: list[str]
    target_seconds: tuple[int, int]
    instructions: str
