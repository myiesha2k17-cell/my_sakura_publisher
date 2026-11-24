"""The two-stage Shorts pipeline: (1) scripts for review, (2) render the approved script."""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from shorts.captions import group_words, write_ass
from shorts.cards import end_card, fit_9x16, font_path, text_card
from shorts.formats import FORMATS
from shorts.models import Book, GuardrailReport, Script, VoiceProfile, WordTiming
from shorts.package import make_zip, post_markdown
from shorts.providers.base import LLM, TTS, ImageGen, TTSResult
from shorts.render import RenderScene, render_video
from shorts.script import ScriptError, check_script, merge_hashtags, write_scripts
from shorts.settings import Settings

END_SECONDS = 2.5
TAIL = 0.3
# Voice + tail + end card must stay under 60 s, with margin for crossfade/encoder rounding.
MAX_AUDIO = 59.3 - END_SECONDS - TAIL  # 56.5 s
MAX_SPEEDUP = 1.12
REVEAL_ROLES = {"cover_reveal", "journal_reveal"}
FLIP_PAGES = [1, 2, 3, 12, 22]
NO_MUSIC = "No music in assets/music — rendered voice only."


@dataclass
class RunResult:
    run_dir: Path
    video: Path
    zip: Path
    post_md: str
    voice_duration: float
    warnings: list[str] = field(default_factory=list)


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def stage1_scripts(book_id: str, format_id: str, n: int, extra: str, llm: LLM,
                   catalog: dict[str, Book], voices: dict[str, VoiceProfile]) -> list[tuple[Script, GuardrailReport]]:
    book = catalog[book_id]
    voice = voices[book.voice]
    results = []
    for script in write_scripts(llm, book, voice, FORMATS[format_id], n=n, extra=extra):
        report = check_script(llm, script, book, voice)
        chosen = report.revised or script
        chosen.post.hashtags = merge_hashtags(chosen, book, voice)
        results.append((chosen, report))
    return results


def _speed_up(result: TTSResult, run_dir: Path) -> TTSResult:
    factor = result.duration / MAX_AUDIO
    if factor > MAX_SPEEDUP:
        raise ScriptError(f"Script too long when spoken ({result.duration:.0f} s). Shorten it to under {MAX_AUDIO:.0f} s.")
    factor = min(MAX_SPEEDUP, factor * 1.01)
    out = run_dir / f"voice_fast{result.audio_path.suffix}"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(result.audio_path), "-filter:a", f"atempo={factor:.4f}",
                    str(out)], check=True)
    words = [WordTiming(word=w.word, start=w.start / factor, end=w.end / factor) for w in result.words]
    return TTSResult(audio_path=out, words=words, duration=result.duration / factor)


def _voice(script: Script, voice: VoiceProfile, tts: TTS, run_dir: Path) -> TTSResult:
    text = " ".join(s.narration.strip() for s in script.scenes if s.narration.strip())
    key = _sha(text + voice.elevenlabs_voice_id)
    cache = run_dir / "audio" / key
    cached = cache.with_suffix(".json")
    if cached.exists():
        data = TTSResultCache.load(cached)
        if data:
            return data
    result = tts.synthesize(text, voice.elevenlabs_voice_id, cache)
    TTSResultCache.save(cached, result)
    return result


class TTSResultCache:
    @staticmethod
    def save(path: Path, result: TTSResult) -> None:
        path.write_text(json.dumps({"audio": str(result.audio_path), "duration": result.duration,
                                    "words": [w.model_dump() for w in result.words]}))

    @staticmethod
    def load(path: Path) -> TTSResult | None:
        data = json.loads(path.read_text())
        audio = Path(data["audio"])
        if not audio.exists():
            return None
        return TTSResult(audio_path=audio, duration=data["duration"],
                         words=[WordTiming(**w) for w in data["words"]])


def _scene_times(script: Script, result: TTSResult) -> list[float]:
    counts = [len(s.narration.split()) for s in script.scenes]
    total = result.duration + TAIL
    if sum(counts) == len(result.words) and result.words:
        starts, idx = [], 0
        for c in counts:
            starts.append(result.words[idx].start if c and idx < len(result.words) else None)
            idx += c
        starts[0] = 0.0
        for i in range(1, len(starts)):       # scenes with no narration share the previous scene's start
            if starts[i] is None:
                starts[i] = starts[i - 1]
        bounds = starts + [total]
        durations = [max(0.6, bounds[i + 1] - bounds[i]) for i in range(len(starts))]
    else:
        weights = [s.seconds or 1.0 for s in script.scenes]
        durations = [total * w / sum(weights) for w in weights]
    scale = total / sum(durations)
    return [d * scale for d in durations]


def _journal_pages(book: Book, run_dir: Path) -> list[Path]:
    if book.page_images:
        return [Path(p) for p in book.page_images]
    csv_path = Path("data") / f"{book.id}_prompts.csv"
    if not csv_path.exists():
        raise ScriptError("Flip-Through needs page images for this book.")
    from master_publisher import run_master_publisher
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    pdf = pages_dir / "journal.pdf"
    if not pdf.exists():
        run_master_publisher(str(csv_path), str(pdf))
    out = []
    for page in FLIP_PAGES:
        target = pages_dir / f"page_{page:02d}.png"
        if not target.exists():
            prefix = pages_dir / f"tmp_{page:02d}"
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile",
                            str(pdf), str(prefix)], check=True)
            prefix.with_suffix(".png").rename(target)
        out.append(target)
    return out


def _scene_images(script: Script, book: Book, images: ImageGen, run_dir: Path) -> list[Path]:
    img_dir = run_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    pages = _journal_pages(book, run_dir) if script.format_id == "flip_through" else []
    has_cover = bool(book.cover) and Path(book.cover).exists()
    paths, page_i = [], 0
    for scene in script.scenes:
        if scene.role == "page" and pages:
            src = pages[page_i % len(pages)]
            page_i += 1
            dst = img_dir / f"page_{page_i}.png"
            if not dst.exists():
                shutil.copy(src, dst)
            paths.append(dst)
        elif (scene.role in REVEAL_ROLES or (pages and scene.role == "cta")) and has_cover:
            paths.append(Path(book.cover))
        elif pages and scene.role == "cta":
            paths.append(paths[-1])
        else:
            dst = img_dir / f"{_sha(scene.image_prompt)}.png"
            if not dst.exists():
                images.generate(scene.image_prompt, dst, book)
            paths.append(dst)
    return paths


def _pick_music(voice: VoiceProfile, music_dir: Path) -> Path | None:
    if not Path(music_dir).is_dir():
        return None
    tracks = sorted(p for p in Path(music_dir).iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".wav"))
    matching = [t for t in tracks if voice.music_mood and voice.music_mood in t.name]
    pool = matching or tracks
    return random.choice(pool) if pool else None


def stage2_render(script: Script, tts: TTS, images: ImageGen, catalog: dict[str, Book],
                  voices: dict[str, VoiceProfile], settings: Settings, music_dir: Path = Path("assets/music"),
                  run_dir: Path | None = None) -> RunResult:
    book = catalog[script.book_id]
    voice = voices[book.voice]
    if run_dir is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = Path(settings.output_dir) / f"{stamp}-{book.id}-{script.format_id}"
    run_dir = Path(run_dir)
    (run_dir / "audio").mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    spoken = _voice(script, voice, tts, run_dir)
    if spoken.duration > MAX_AUDIO:
        spoken = _speed_up(spoken, run_dir)

    durations = _scene_times(script, spoken)
    sources = _scene_images(script, book, images, run_dir)
    color = voice.palette[-1] if voice.palette else "#FFFFFF"
    cards_dir = run_dir / "cards"
    scenes = []
    for i, (scene, src, seconds) in enumerate(zip(script.scenes, sources, durations)):
        image = src
        if scene.on_screen_text.strip():
            base = fit_9x16(src, cards_dir / f"base_{i}.png")
            image = text_card(scene.on_screen_text, base, cards_dir / f"card_{i}.png", font_path(voice.font), color)
        scenes.append(RenderScene(image=image, seconds=seconds))

    ass = write_ass(group_words(spoken.words), run_dir / "captions.ass", font=voice.font,
                    primary=color, outline=voice.palette[0] if voice.palette else "#000000")
    end = end_card(book, voice, cards_dir / "end.png")
    music = _pick_music(voice, music_dir)
    if music is None:
        warnings.append(NO_MUSIC)

    video = render_video(scenes, spoken.audio_path, ass, run_dir / "short.mp4", music=music, end_card=end,
                         end_seconds=END_SECONDS)
    post_md = post_markdown(script, book)
    (run_dir / "post.md").write_text(post_md, encoding="utf-8")
    (run_dir / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")
    return RunResult(run_dir=run_dir, video=video, zip=make_zip(run_dir), post_md=post_md,
                     voice_duration=spoken.duration, warnings=warnings)
