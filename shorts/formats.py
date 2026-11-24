"""Short-video format templates. Each format is a beat structure plus direction for the script writer."""
from __future__ import annotations

from shorts.models import BookType, Format

_FORMATS = [
    Format(
        id="trope_hook", name="Trope Hook", book_types=["fiction"],
        beats=["hook", "trope", "trope", "trope", "cover_reveal", "cta"], target_seconds=(20, 35),
        instructions=(
            "Open with a 'POV:' or 'If you want a book where…' hook built from the book's real tropes. "
            "Give three quick trope beats, each one short line on screen. Reveal the cover, then the call to action."
        ),
    ),
    Format(
        id="read_this_line", name="Read This Line", book_types=["fiction", "nonfiction", "devotional"],
        beats=["hook", "quote", "quote", "context", "cover_reveal", "cta"], target_seconds=(20, 40),
        instructions=(
            "Hook with why this line stopped you. Show one to three lines from the book EXACTLY as written in the quotes list, "
            "as large on-screen text with slow narration. Add one spoiler-free line of context, then the cover and call to action."
        ),
    ),
    Format(
        id="books_that_feel_like", name="Books That Feel Like…", book_types=["fiction"],
        beats=["hook", "vibe", "vibe", "vibe", "vibe", "cover_reveal", "cta"], target_seconds=(20, 35),
        instructions=(
            "A vibes montage: 'This book feels like…' followed by four sensory, aesthetic images drawn from the blurb "
            "(places, objects, weather, light). Each vibe is a short phrase on screen. End on the cover."
        ),
    ),
    Format(
        id="word_for_today", name="Word for Today", book_types=["devotional"],
        beats=["hook", "word", "reflection", "reflection", "cta"], target_seconds=(20, 40),
        instructions=(
            "A gentle morning word: one encouraging line from the quotes list, a short reflection in the author's voice "
            "spoken to one listener, and the author's sign-off."
        ),
    ),
    Format(
        id="prompt_of_the_day", name="Prompt of the Day", book_types=["journal"],
        beats=["hook", "prompt", "pause", "reflection", "journal_reveal", "cta"], target_seconds=(20, 35),
        instructions=(
            "Invite the viewer to pause and answer one journal prompt taken EXACTLY from the quotes list. "
            "Show the prompt large, leave a breath of silence-feeling, offer one gentle reflection, then reveal the journal."
        ),
    ),
    Format(
        id="flip_through", name="Flip-Through", book_types=["journal", "coloring"],
        beats=["page", "page", "page", "page", "page", "cta"], target_seconds=(20, 35),
        instructions=(
            "A calm flip-through of real interior pages. Narration describes what the reader will do on these pages "
            "(no invented features). On-screen text is a short label per page."
        ),
    ),
    Format(
        id="idea_in_30", name="Idea in 30 Seconds", book_types=["nonfiction"],
        beats=["hook", "idea", "example", "takeaway", "cta"], target_seconds=(20, 35),
        instructions=(
            "Lead with a contrarian or surprising hook taken from the book's real ideas. Explain the idea, give one concrete "
            "example, and leave one takeaway the viewer can use today."
        ),
    ),
]

FORMATS: dict[str, Format] = {f.id: f for f in _FORMATS}


def formats_for(book_type: BookType) -> list[Format]:
    return [f for f in _FORMATS if book_type in f.book_types]
