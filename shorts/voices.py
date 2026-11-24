"""Load author voice profiles from voices/*.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

from shorts.models import VoiceProfile


def load_voices(dir: Path = Path("voices")) -> dict[str, VoiceProfile]:
    voices: dict[str, VoiceProfile] = {}
    for path in sorted(Path(dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("id", path.stem)
        profile = VoiceProfile(**data)
        voices[profile.id] = profile
    return voices
