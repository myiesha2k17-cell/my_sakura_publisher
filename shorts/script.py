"""Write short-video scripts in an author's voice, and check them against the book's facts."""
from __future__ import annotations

import re

from pydantic import ValidationError

from shorts.formats import FORMATS
from shorts.models import Book, Format, GuardrailReport, GuardrailReview, Script, ScriptDraft, VoiceProfile
from shorts.providers.base import LLM, Refusal

BRAND = "Hanako Design & Media"
BRAND_TAG = "#HanakoDesignAndMedia"
MAX_TAGS = 8
_QUOTED = re.compile(r'"([^"]{3,})"')


class ScriptError(Exception):
    pass


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- (none)"


def build_prompt(book: Book, voice: VoiceProfile, fmt: Format, extra: str = "") -> tuple[str, str]:
    system = (
        f"You write short vertical videos (TikTok, Instagram Reels, YouTube Shorts) for {BRAND}, "
        f"an independent publisher. You write in the voice of {voice.display_name}.\n\n"
        f"Persona: {voice.persona}\n"
        f"Tone: {voice.tone}\n"
        f"Words that fit this voice: {', '.join(voice.use_words)}\n"
        f"Never use these words or phrases: {', '.join(voice.avoid_words)}\n"
        f"Signature phrases you may use sparingly: {', '.join(voice.signature_phrases)}\n"
        f"Sign-off: {voice.sign_off}\n\n"
        "Rules:\n"
        "- Use only facts from the book entry you are given. Never invent plot, characters, reviews, awards, "
        "sales figures or rankings.\n"
        "- Any line shown in quotation marks must be copied exactly from the book's quote list.\n"
        "- The first scene is the hook and must stop the scroll within two seconds.\n"
        "- Write narration to be spoken aloud: short sentences, no hashtags, no emoji, no stage directions.\n"
        "- On-screen text is short (at most about 12 words) and must not repeat the narration word for word.\n"
        "- Image prompts describe a mood scene with no text, letters or logos in the image.\n"
        "- Captions should invite saves and comments, and point to the link in bio."
    )
    user = (
        f"Book: {book.title}" + (f" ({book.series})" if book.series else "") + f"\n"
        f"Author: {book.author}\n"
        f"Type: {book.book_type}\n"
        f"Blurb:\n{book.blurb}\n\n"
        f"Tropes / keywords:\n{_bullets(book.tropes)}\n\n"
        f"Quotes (verbatim — copy exactly if you use one):\n{_bullets(book.quotes)}\n\n"
        f"Never mention:\n{_bullets(book.do_not_say)}\n\n"
        f"Format: {fmt.name}\n{fmt.instructions}\n"
        f"Scenes, in order, one per beat: {', '.join(fmt.beats)}\n"
        f"Total length: {fmt.target_seconds[0]}–{fmt.target_seconds[1]} seconds when spoken.\n\n"
        f"Everything posts from the single {BRAND} account. The final scene's call to action is "
        f"'Link in bio' and presents the book as {book.author}'s, from {BRAND}.\n"
        f"Suggested hashtags: {' '.join(book.hashtags + voice.default_hashtags)}"
    )
    if extra.strip():
        user += f"\n\nExtra direction from the publisher: {extra.strip()}"
    return system, user


def _fit_seconds(draft: ScriptDraft, fmt: Format) -> ScriptDraft:
    total = sum(s.seconds for s in draft.scenes) or 1.0
    lo, hi = fmt.target_seconds
    target = min(max(total, lo), hi)
    if target != total:
        for scene in draft.scenes:
            scene.seconds = round(scene.seconds * target / total, 2)
    return draft


def _ask(llm: LLM, system: str, user: str, schema):
    last_error: Exception | None = None
    for _ in range(2):
        try:
            return llm.parse(system, user, schema)
        except Refusal as e:
            raise ScriptError(f"The model declined to write this script ({e}). Try different direction.") from e
        except ValidationError as e:
            last_error = e
    raise ScriptError("The model could not produce a valid script after 2 tries. Please try again.") from last_error


def write_scripts(llm: LLM, book: Book, voice: VoiceProfile, fmt: Format, n: int = 1,
                  extra: str = "") -> list[Script]:
    system, user = build_prompt(book, voice, fmt, extra)
    scripts: list[Script] = []
    for _ in range(n):
        prompt = user
        if scripts:
            used = "\n".join(f"- {s.hook}" for s in scripts)
            prompt += f"\n\nWrite a different angle from these earlier hooks:\n{used}"
        draft = _fit_seconds(_ask(llm, system, prompt, ScriptDraft), fmt)
        scripts.append(Script(**draft.model_dump(), book_id=book.id, format_id=fmt.id))
    return scripts


def _norm(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return " ".join(text.split())


def _quote_flags(script: Script, book: Book) -> list[str]:
    known = [_norm(q).lower() for q in book.quotes]
    flags = []
    texts = [script.hook, script.cta] + [t for s in script.scenes for t in (s.narration, s.on_screen_text)]
    for text in texts:
        for quoted in _QUOTED.findall(_norm(text)):
            if not any(quoted.strip().lower() in q for q in known):
                flags.append(f'Quoted line is not in the book\'s quote list: "{quoted.strip()}"')
    return flags


def check_script(llm: LLM, script: Script, book: Book, voice: VoiceProfile) -> GuardrailReport:
    flags = _quote_flags(script, book)
    system = (
        f"You are the fact and voice editor for {BRAND}. Compare a short-video script against the book entry "
        "and the author's voice profile. Flag: claims not supported by the book entry, spoilers or anything on the "
        "'Never mention' list, quotes not copied exactly, words the voice avoids, and anything that reads as generic "
        "marketing. If there are problems, return a revised script that fixes them; otherwise return no revision."
    )
    _, book_entry = build_prompt(book, voice, FORMATS[script.format_id])
    user = (f"{book_entry}\n\nVoice tone: {voice.tone}\nAvoid: {', '.join(voice.avoid_words)}\n\n"
            f"Script to review (JSON):\n{script.model_dump_json(indent=2)}")
    review = _ask(llm, system, user, GuardrailReview)
    flags += review.flags
    revised = None
    if review.revised is not None and flags:
        revised = Script(**review.revised.model_dump(), book_id=script.book_id, format_id=script.format_id)
    return GuardrailReport(ok=not flags, flags=flags, revised=revised)


def merge_hashtags(script: Script, book: Book, voice: VoiceProfile) -> list[str]:
    no_booktok = book.book_type in ("journal", "coloring")
    tags: list[str] = []
    seen: set[str] = set()
    for raw in [BRAND_TAG] + book.hashtags + script.post.hashtags + voice.default_hashtags:
        tag = "#" + raw.strip().lstrip("#").replace(" ", "")
        key = tag.lower()
        if len(tag) < 2 or key in seen or (no_booktok and "booktok" in key):
            continue
        seen.add(key)
        tags.append(tag)
    return tags[:MAX_TAGS]
