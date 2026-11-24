"""Compose the final 1080x1920 MP4 with ffmpeg: Ken Burns scenes, crossfades, captions, end card, voice + music."""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from shorts.cards import fit_9x16

W, H, FPS = 1080, 1920, 30
FADE = 0.4
MUSIC_VOLUME = 0.12


class RenderError(Exception):
    pass


@dataclass
class RenderScene:
    image: Path
    seconds: float


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-20:])
        raise RenderError(f"ffmpeg failed:\n{tail}")


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    audio = [s for s in data["streams"] if s["codec_type"] == "audio"]
    num, den = video["r_frame_rate"].split("/")
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": round(int(num) / int(den)),
        "duration": float(data["format"]["duration"]),
        "has_audio": bool(audio),
        "audio_streams": len(audio),
    }


def _zoompan(index: int, frames: int) -> str:
    """Slow zoom with a direction that alternates per scene."""
    zoom = f"min(1+0.10*on/{frames},1.10)"
    if index % 3 == 0:      # centre push-in
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif index % 3 == 1:    # drift upward
        x, y = "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*(1-on/{frames})"
    else:                   # drift left to right
        x, y = f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
    return (f"scale={round(W * 1.1)}:{round(H * 1.1)},"
            f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS},setsar=1")


def _scene_clip(index: int, image: Path, seconds: float, out: Path) -> Path:
    frames = max(1, round(seconds * FPS))
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-vf", _zoompan(index, frames),
          "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
          "-crf", "18", str(out)])
    return out


def render_video(scenes: list[RenderScene], voice_audio: Path, captions_ass: Path, out: Path,
                 music: Path | None = None, end_card: Path | None = None, end_seconds: float = 2.5) -> Path:
    if not scenes:
        raise RenderError("No scenes to render.")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        tmp = Path(tmp)
        clips = []
        for i, scene in enumerate(scenes):
            fitted = fit_9x16(scene.image, tmp / f"fit_{i}.png")
            extra = FADE if i < len(scenes) - 1 else 0.0   # crossfades overlap, so pad all but the last
            clips.append(_scene_clip(i, fitted, scene.seconds + extra, tmp / f"scene_{i}.mp4"))
        if end_card is not None:
            end_fit = fit_9x16(end_card, tmp / "end_fit.png")
            end_clip = tmp / "end.mp4"
            _run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(end_fit), "-t", f"{end_seconds:.3f}",
                  "-vf", f"fps={FPS},fade=t=in:st=0:d=0.3,setsar=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                  "-preset", "veryfast", "-crf", "18", str(end_clip)])

        scenes_total = sum(s.seconds for s in scenes)
        total = scenes_total + (end_seconds if end_card is not None else 0.0)

        cmd = ["ffmpeg", "-y", "-v", "error"]
        for clip in clips:
            cmd += ["-i", str(clip)]
        if end_card is not None:
            cmd += ["-i", str(end_clip)]
        voice_idx = len(clips) + (1 if end_card is not None else 0)
        cmd += ["-i", str(voice_audio)]
        if music is not None:
            cmd += ["-stream_loop", "-1", "-i", str(music)]

        graph = []
        last = "[0:v]"
        offset = 0.0
        for i in range(1, len(clips)):
            offset += scenes[i - 1].seconds
            label = f"[x{i}]"
            # Each clip but the last is FADE longer, so the cumulative scene time is the crossfade start.
            graph.append(f"{last}[{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}{label}")
            last = label
        ass_path = str(captions_ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        graph.append(f"{last}ass='{ass_path}',trim=duration={scenes_total:.3f},setpts=PTS-STARTPTS[body]")
        if end_card is not None:
            graph.append(f"[body][{len(clips)}:v]concat=n=2:v=1:a=0[vout]")
        else:
            graph.append("[body]null[vout]")

        if music is not None:
            graph.append(f"[{voice_idx}:a]aresample=44100,asplit=2[vkey][vmix]")
            graph.append(f"[{voice_idx + 1}:a]aresample=44100,volume={MUSIC_VOLUME}[mus]")
            graph.append("[mus][vkey]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[duck]")
            graph.append("[vmix][duck]amix=inputs=2:duration=longest:normalize=0,apad[aout]")
        else:
            graph.append(f"[{voice_idx}:a]aresample=44100,apad[aout]")

        cmd += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
                "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", str(out)]
        _run(cmd)
    return out
