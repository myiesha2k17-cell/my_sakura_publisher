"""Still images for the short: 9:16 fitting, text cards and the branded end card (Pillow)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from shorts.models import Book, VoiceProfile

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 250, 1520, 60, 960
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
BRAND = "Hanako Design & Media"


def font_path(name: str) -> Path:
    path = FONT_DIR / f"{name}.ttf"
    return path if path.exists() else FONT_DIR / "DejaVuSans-Bold.ttf"


def _cover_fill(img: Image.Image) -> Image.Image:
    scale = max(W / img.width, H / img.height)
    resized = img.resize((max(W, round(img.width * scale)), max(H, round(img.height * scale))), Image.LANCZOS)
    left, top = (resized.width - W) // 2, (resized.height - H) // 2
    return resized.crop((left, top, left + W, top + H))


def _blur_bg(img: Image.Image) -> Image.Image:
    bg = _cover_fill(img).filter(ImageFilter.GaussianBlur(40))
    return ImageEnhance.Brightness(bg).enhance(0.55)


def fit_9x16(src: Path, out: Path) -> Path:
    img = Image.open(src).convert("RGB")
    canvas = _blur_bg(img)
    scale = min(W / img.width, H / img.height)
    fg = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(draw, text: str, font_file: Path, max_w: int, max_h: int, start: int = 84):
    size = start
    while size >= 28:
        font = ImageFont.truetype(str(font_file), size)
        lines = _wrap(draw, text, font, max_w)
        line_h = round(size * 1.25)
        if len(lines) * line_h <= max_h and all(draw.textlength(l, font=font) <= max_w for l in lines):
            return font, lines, line_h
        size -= 4
    font = ImageFont.truetype(str(font_file), 28)
    return font, _wrap(draw, text, font, max_w), 35


def text_card(text: str, base: Path, out: Path, font_path: Path, color: str) -> Path:
    img = Image.open(base).convert("RGBA").resize((W, H))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    pad = 40
    max_w = SAFE_RIGHT - SAFE_LEFT - 2 * pad
    max_h = SAFE_BOTTOM - SAFE_TOP - 2 * pad
    font, lines, line_h = _fit_text(draw, text, font_path, max_w, max_h)
    block_h = len(lines) * line_h
    top = SAFE_TOP + (SAFE_BOTTOM - SAFE_TOP - block_h) // 2
    widest = max((draw.textlength(l, font=font) for l in lines), default=0)
    cx = (SAFE_LEFT + SAFE_RIGHT) // 2
    draw.rounded_rectangle(
        (cx - widest / 2 - pad, top - pad, cx + widest / 2 + pad, top + block_h + pad),
        radius=28, fill=(0, 0, 0, 150),
    )
    for i, line in enumerate(lines):
        draw.text((cx, top + i * line_h), line, font=font, fill=color, anchor="ma")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(img, overlay).convert("RGB").save(out)
    return out


def end_card(book: Book, voice: VoiceProfile, out: Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    line = f"Link in bio · {book.author} · {BRAND}"
    accent = voice.palette[0] if voice.palette else "#222222"
    text_color = voice.palette[-1] if voice.palette else "#FFFFFF"
    if book.cover and Path(book.cover).exists():
        cover = Image.open(book.cover).convert("RGB")
        canvas = _blur_bg(cover)
        cw = round(W * 0.6)
        ch = round(cover.height * cw / cover.width)
        max_ch = 1000
        if ch > max_ch:
            cw, ch = round(cw * max_ch / ch), max_ch
        canvas.paste(cover.resize((cw, ch), Image.LANCZOS), ((W - cw) // 2, SAFE_TOP + 20))
        text_top = SAFE_TOP + 20 + ch + 50
    else:
        canvas = Image.new("RGB", (W, H), accent)
        text_top = SAFE_TOP + 200
        title_font = ImageFont.truetype(str(font_path(voice.font)), 90)
        ImageDraw.Draw(canvas).text((W // 2, text_top), book.title, font=title_font, fill=text_color, anchor="ma")
        text_top += 200
    draw = ImageDraw.Draw(canvas)
    font, lines, line_h = _fit_text(draw, line, font_path(voice.font), SAFE_RIGHT - SAFE_LEFT,
                                    SAFE_BOTTOM - text_top, start=48)
    for i, l in enumerate(lines):
        draw.text(((SAFE_LEFT + SAFE_RIGHT) // 2, text_top + i * line_h), l, font=font, fill=text_color, anchor="ma",
                  stroke_width=3, stroke_fill="#000000")
    canvas.save(out)
    out.with_suffix(".txt").write_text(line, encoding="utf-8")
    return out
