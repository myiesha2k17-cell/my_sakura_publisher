from pathlib import Path

from PIL import Image

from shorts.cards import end_card, fit_9x16, font_path, text_card
from shorts.catalog import load_catalog
from shorts.voices import load_voices


def test_fit_9x16_sizes(tmp_path):
    for size in [(1600, 2560), (1024, 1536), (200, 100)]:
        src = tmp_path / f"src_{size[0]}.png"
        Image.new("RGB", size, "#3E5A6B").save(src)
        out = fit_9x16(src, tmp_path / f"out_{size[0]}.png")
        assert Image.open(out).size == (1080, 1920)


def test_font_path_exists():
    assert font_path("DejaVuSerif-Bold").exists()
    assert font_path("DejaVuSans-Bold").exists()


def test_text_card_inside_safe_zone(tmp_path):
    base = tmp_path / "black.png"
    Image.new("RGB", (1080, 1920), "black").save(base)
    long_text = "You can build a life on proof, and still owe something you can't prove exists. " * 3
    out = text_card(long_text, base, tmp_path / "card.png", font_path("DejaVuSerif-Bold"), "#F4EAD5")
    img = Image.open(out).convert("L")
    assert img.size == (1080, 1920)
    left, top, right, bottom = img.point(lambda v: 255 if v > 10 else 0).getbbox()
    assert top >= 250 and bottom <= 1520
    assert left >= 60 and right <= 960


def test_text_card_special_chars(tmp_path):
    base = tmp_path / "black.png"
    Image.new("RGB", (1080, 1920), "black").save(base)
    out = text_card("Counterparty: Èṣù. Ọṣun.", base, tmp_path / "card.png", font_path("DejaVuSans-Bold"), "#FFFFFF")
    assert Image.open(out).size == (1080, 1920)


def test_end_card_text(tmp_path):
    book = load_catalog()["the_ledger"]
    voice = load_voices()["ren_hawthorne"]
    out = end_card(book, voice, tmp_path / "end.png")
    assert Image.open(out).size == (1080, 1920)
    assert (tmp_path / "end.txt").read_text() == "Link in bio · Ren Hawthorne · Hanako Design & Media"
