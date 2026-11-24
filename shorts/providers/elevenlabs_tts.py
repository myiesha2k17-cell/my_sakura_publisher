"""ElevenLabs text-to-speech with character timestamps, turned into word timings."""
from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import requests

from shorts.models import WordTiming
from shorts.providers.base import ProviderError, TTSResult

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"


def audio_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def words_from_alignment(alignment: dict) -> list[WordTiming]:
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    words: list[WordTiming] = []
    current, w_start, w_end = "", 0.0, 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if current:
                words.append(WordTiming(word=current, start=w_start, end=w_end))
                current = ""
            continue
        if not current:
            w_start = s
        current += ch
        w_end = e
    if current:
        words.append(WordTiming(word=current, start=w_start, end=w_end))
    return words


class ElevenLabsTTS:
    def __init__(self, api_key: str, model_id: str = "eleven_multilingual_v2"):
        self.api_key = api_key
        self.model_id = model_id

    def synthesize(self, text: str, voice_id: str, out_path: Path) -> TTSResult:
        if not voice_id:
            raise ProviderError("No ElevenLabs voice ID set for this author. Add elevenlabs_voice_id to the voice file.")
        try:
            response = requests.post(
                API.format(voice_id=voice_id),
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": self.model_id},
                timeout=120,
            )
        except requests.RequestException as e:
            raise ProviderError("Could not reach ElevenLabs. Check the network and try again.") from e
        if response.status_code != 200:
            raise ProviderError(f"ElevenLabs returned an error ({response.status_code}). "
                                "Check the API key, voice ID and character quota.")
        data = response.json()
        out_path = Path(out_path).with_suffix(".mp3")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(data["audio_base64"]))
        words = words_from_alignment(data.get("alignment") or {})
        return TTSResult(audio_path=out_path, words=words, duration=audio_duration(out_path))
