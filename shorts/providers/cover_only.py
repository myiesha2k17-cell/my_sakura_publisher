"""Scene images made only from the book cover — no image service or key needed."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from shorts.models import Book

OUT_W, OUT_H = 1024, 1536
# (left, top, right, bottom) as fractions of the cover
CROPS = [
    (0.0, 0.0, 1.0, 1.0),       # full cover
    (0.15, 0.30, 0.85, 0.80),   # centre
    (0.0, 0.0, 1.0, 0.45),      # top third
    (0.0, 0.55, 1.0, 1.0),      # bottom third
    (0.0, 0.25, 0.6, 0.75),     # left detail
    (0.4, 0.25, 1.0, 0.75),     # right detail
]


class CoverOnlyImages:
    def __init__(self):
        self.count = 0

    def generate(self, prompt: str, out_path: Path, book: Book) -> Path:
        index = self.count
        self.count += 1
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not book.cover or not Path(book.cover).exists():
            shade = 40 + (index * 23) % 60
            img = Image.linear_gradient("L").resize((OUT_W, OUT_H)).point(lambda v: shade + v // 4)
            ImageOps.colorize(img, "#1b1428", "#7a5a6a").save(out_path)
            return out_path
        cover = Image.open(book.cover).convert("RGB")
        l, t, r, b = CROPS[index % len(CROPS)]
        crop = cover.crop((round(l * cover.width), round(t * cover.height),
                           round(r * cover.width), round(b * cover.height)))
        img = ImageOps.fit(crop, (OUT_W, OUT_H), Image.LANCZOS)
        if index % len(CROPS):
            img = img.filter(ImageFilter.GaussianBlur(1.5 + (index % 3)))
        avg = img.resize((1, 1)).getpixel((0, 0))
        tint = Image.new("RGB", img.size, avg)
        img = Image.blend(img, tint, 0.12 + 0.04 * (index % 3))
        img = ImageEnhance.Brightness(img).enhance(0.85 + 0.05 * (index % 4))
        img.save(out_path)
        return out_path
