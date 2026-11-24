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


class Scene(BaseModel):
    role: str = Field(description="The beat this scene plays, e.g. hook, trope, quote, cover_reveal, cta")
    narration: str = Field(description="What the narrator says in this scene, in the author's voice")
    on_screen_text: str = Field(description="Short bold text shown on screen (max ~12 words)")
    image_prompt: str = Field(description="Visual description for the background image, no text in the image")
    seconds: float = Field(description="Approximate length of this scene in seconds")


class PostText(BaseModel):
    tiktok_caption: str
    instagram_caption: str
    youtube_title: str
    youtube_description: str
    hashtags: list[str] = Field(default_factory=list)


class ScriptDraft(BaseModel):
    """What the model writes. book_id/format_id are added by our code, never trusted from the model."""
    hook: str
    scenes: list[Scene]
    cta: str
    post: PostText


class Script(ScriptDraft):
    book_id: str
    format_id: str


class GuardrailReview(BaseModel):
    """What the model returns when reviewing a script."""
    flags: list[str] = Field(default_factory=list, description="Each problem found, one sentence each")
    revised: ScriptDraft | None = Field(default=None, description="A corrected script, only if there were problems")


class GuardrailReport(BaseModel):
    ok: bool
    flags: list[str]
    revised: Script | None = None
