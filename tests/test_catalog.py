from pathlib import Path

import pytest

from shorts.catalog import load_catalog
from shorts.voices import load_voices


def test_loads_two_ren_books():
    catalog = load_catalog()
    for book_id in ("the_ledger", "the_ones_nobody_came_for"):
        book = catalog[book_id]
        assert book.author == "Ren Hawthorne"
        assert book.voice == "ren_hawthorne"
        assert book.book_type == "fiction"
        assert Path(book.cover).exists()
    assert catalog["the_ledger"].amazon_url == "https://a.co/d/0dXjLJ2d"
    assert catalog["the_ones_nobody_came_for"].amazon_url == "https://a.co/d/0aPWMork"


def test_ledger_quotes_verbatim():
    assert "Not superstition. Bookkeeping." in load_catalog()["the_ledger"].quotes


def test_sakura_auto_entries():
    book = load_catalog()["sakura_calm"]
    assert book.book_type == "journal"
    assert book.voice == "hanako"
    assert len(book.quotes) == 30
    assert book.quotes[0] == "What does 'peace' feel like in your body right now?"
    assert not any("BookTok" in tag for tag in book.hashtags)


def test_all_voices_load():
    voices = load_voices()
    assert set(voices) == {"ren_hawthorne", "aris_thorne", "julian_thorne", "elias_thorne", "hanako"}
    for book in load_catalog().values():
        assert book.voice in voices


def test_unknown_voice_rejected(tmp_path):
    bad = tmp_path / "books.yaml"
    bad.write_text(
        "- id: mystery\n  title: Mystery\n  author: X\n  voice: nobody\n  book_type: fiction\n"
        "  blurb: b\n  tropes: []\n  quotes: []\n  cover: ''\n"
    )
    with pytest.raises(ValueError, match="mystery"):
        load_catalog(bad, data_dir=tmp_path)
