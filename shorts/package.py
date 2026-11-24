"""Post text and the downloadable zip."""
from __future__ import annotations

import zipfile
from pathlib import Path

from shorts.models import Book, Script

AI_REMINDER = 'Reminder: turn on the platform\'s "AI-generated content" label (AI voice/images used).'


def post_markdown(script: Script, book: Book) -> str:
    tags = " ".join(script.post.hashtags)
    link = f"\n\n{book.title} on Amazon: {book.amazon_url}" if book.amazon_url else ""
    return (
        f"# {book.title} — {script.format_id.replace('_', ' ').title()}\n\n"
        f"## TikTok\n\n{script.post.tiktok_caption}\n\n{tags}\n\n"
        f"## Instagram\n\n{script.post.instagram_caption}\n\n{tags}\n\n"
        f"## YouTube Shorts\n\n**Title:** {script.post.youtube_title[:100]}\n\n"
        f"**Description:**\n\n{script.post.youtube_description}{link}\n\n{tags}\n\n"
        f"---\n\n{AI_REMINDER}\n"
    )


def make_zip(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    out = run_dir / f"{run_dir.name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("short.mp4", "post.md", "script.json"):
            if (run_dir / name).exists():
                z.write(run_dir / name, name)
        for img in sorted((run_dir / "images").glob("*")):
            z.write(img, f"images/{img.name}")
    return out
