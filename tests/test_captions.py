import subprocess

from shorts.captions import group_words, write_ass
from shorts.models import WordTiming


def words(*ws, step=0.5):
    return [WordTiming(word=w, start=i * step, end=i * step + 0.4) for i, w in enumerate(ws)]


def test_group_words():
    phrases = group_words(words("a", "b", "c", "d", "e", "f", "g"))
    assert len(phrases) == 3
    assert phrases[0].start == 0.0 and phrases[0].end == 1.4
    assert phrases[0].word == "a b c"
    assert phrases[2].word == "g" and phrases[2].start == 3.0


def test_group_words_respects_char_limit():
    phrases = group_words(words("superstition.", "Bookkeeping.", "yes"), max_words=3, max_chars=18)
    assert phrases[0].word == "superstition."


def test_ass_escapes(tmp_path):
    out = write_ass([WordTiming(word="Èṣù {owes} a\\debt, really", start=0.0, end=0.9)], tmp_path / "c.ass",
                    font="DejaVuSerif-Bold", primary="#F4EAD5", outline="#2B2560")
    text = out.read_text(encoding="utf-8")
    assert "Èṣù" in text
    assert "\\{owes\\}" in text
    assert "a\\debt" not in text  # a raw backslash would start an ASS override tag
    assert "debt, really" in text
    result = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1",
                             "-vf", f"ass={out}", "-f", "null", "-"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_ass_safe_zone(tmp_path):
    text = write_ass(words("hello"), tmp_path / "c.ass", font="DejaVuSans-Bold",
                     primary="#FFFFFF", outline="#000000").read_text()
    assert "PlayResY: 1920" in text and "PlayResX: 1080" in text
    style = next(line for line in text.splitlines() if line.startswith("Style:")).split(",")
    # Style fields: ... Alignment, MarginL, MarginR, MarginV, Encoding
    assert style[-5:-1] == ["2", "60", "120", "520"]
