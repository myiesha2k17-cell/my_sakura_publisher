"""Load the book catalog: hand-written entries plus auto entries for Sakura journals."""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

from shorts.models import Book
from shorts.voices import load_voices

SAKURA_HASHTAGS = ["#JournalPrompts", "#Journaling", "#SelfCare", "#GuidedJournal", "#HanakoDesignAndMedia"]


def _sakura_books(data_dir: Path) -> list[Book]:
    books = []
    for csv_path in sorted(Path(data_dir).glob("sakura_*_prompts.csv")):
        book_id = csv_path.stem.removesuffix("_prompts")
        topic = book_id.removeprefix("sakura_").replace("_", " ").title()
        with open(csv_path, encoding="utf-8") as f:
            prompts = [row["Prompt"].strip() for row in csv.DictReader(f) if row.get("Prompt", "").strip()]
        cover = Path("assets/covers/sakura.jpg")
        books.append(Book(
            id=book_id,
            title=f"Sakura {topic} Journal",
            series="Sakura Series",
            author="Hanako Design & Media",
            voice="hanako",
            book_type="journal",
            blurb="A 30-day guided journal from the Sakura Series.",
            quotes=prompts,
            hashtags=list(SAKURA_HASHTAGS),
            cover=str(cover) if cover.exists() else "",
        ))
    return books


def load_catalog(path: Path = Path("catalog/books.yaml"), data_dir: Path = Path("data"),
                 voices_dir: Path = Path("voices")) -> dict[str, Book]:
    entries = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    books = [Book(**entry) for entry in entries] + _sakura_books(data_dir)
    known_voices = set(load_voices(voices_dir))
    catalog: dict[str, Book] = {}
    for book in books:
        if book.voice not in known_voices:
            raise ValueError(f"Book '{book.id}' uses unknown voice '{book.voice}'")
        catalog[book.id] = book
    return catalog
