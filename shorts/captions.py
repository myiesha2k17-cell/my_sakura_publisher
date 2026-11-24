"""Word-timed captions as an ASS subtitle file (rendered by ffmpeg's libass)."""
from __future__ import annotations

from pathlib import Path

from shorts.models import WordTiming

WIDTH, HEIGHT = 1080, 1920
MARGIN_L, MARGIN_R, MARGIN_V = 60, 120, 520

_FONT_FAMILIES = {
    "DejaVuSerif-Bold": ("DejaVu Serif", True),
    "DejaVuSerif": ("DejaVu Serif", False),
    "DejaVuSans-Bold": ("DejaVu Sans", True),
    "DejaVuSans": ("DejaVu Sans", False),
}


def group_words(words: list[WordTiming], max_words: int = 3, max_chars: int = 18) -> list[WordTiming]:
    phrases: list[WordTiming] = []
    current: list[WordTiming] = []
    for w in words:
        candidate = " ".join(x.word for x in current + [w])
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            phrases.append(_join(current))
            current = []
        current.append(w)
    if current:
        phrases.append(_join(current))
    return phrases


def _join(ws: list[WordTiming]) -> WordTiming:
    return WordTiming(word=" ".join(w.word for w in ws), start=ws[0].start, end=ws[-1].end)


def _ass_color(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _escape(text: str) -> str:
    # A backslash would start an ASS override tag; swap it for a look-alike character.
    text = text.replace("\\", "\u29f5")
    return text.replace("{", "\\{").replace("}", "\\}").replace("\n", " ")


def _ts(seconds: float) -> str:
    cs = max(0, round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def write_ass(phrases: list[WordTiming], out: Path, font: str, primary: str, outline: str) -> Path:
    family, bold = _FONT_FAMILIES.get(font, ("DejaVu Sans", True))
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {WIDTH}\nPlayResY: {HEIGHT}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        f"Style: Caption,{family},78,{_ass_color(primary)},{_ass_color(primary)},{_ass_color(outline)},&H80000000,"
        f"{-1 if bold else 0},0,0,0,100,100,0,0,1,6,2,2,{MARGIN_L},{MARGIN_R},{MARGIN_V},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    pop = "{\\fscx110\\fscy110\\t(0,120,\\fscx100\\fscy100)}"
    lines = [f"Dialogue: 0,{_ts(p.start)},{_ts(p.end)},Caption,,0,0,0,,{pop}{_escape(p.word)}" for p in phrases]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out
