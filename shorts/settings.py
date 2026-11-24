"""Configuration from Streamlit secrets / environment, plus the daily generation cap."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

DEFAULT_MODEL = "claude-opus-5-5"


@dataclass
class Settings:
    anthropic_key: str | None
    elevenlabs_key: str | None
    openai_key: str | None
    password: str | None
    daily_cap: int
    claude_model: str
    output_dir: Path

    @classmethod
    def from_sources(cls, env: Mapping[str, str], secrets: Mapping[str, str] | None) -> "Settings":
        merged = {**{k: v for k, v in env.items()}, **dict(secrets or {})}

        def get(name: str) -> str | None:
            value = merged.get(name)
            return str(value).strip() or None if value is not None else None

        return cls(
            anthropic_key=get("ANTHROPIC_API_KEY"),
            elevenlabs_key=get("ELEVENLABS_API_KEY"),
            openai_key=get("OPENAI_API_KEY"),
            password=get("SHORTS_PASSWORD"),
            daily_cap=int(get("SHORTS_DAILY_CAP") or 10),
            claude_model=get("SHORTS_CLAUDE_MODEL") or DEFAULT_MODEL,
            output_dir=Path(get("SHORTS_OUTPUT_DIR") or "output"),
        )

    def missing_for_script(self) -> list[str]:
        return [] if self.anthropic_key else ["ANTHROPIC_API_KEY"]

    def missing_for_render(self) -> list[str]:
        return [] if self.elevenlabs_key else ["ELEVENLABS_API_KEY"]


class CapReached(Exception):
    pass


class DailyCap:
    def __init__(self, path: Path, limit: int):
        self.path = Path(path)
        self.limit = limit

    def _count(self, today: date) -> int:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return 0
        return int(data.get("count", 0)) if data.get("date") == today.isoformat() else 0

    def remaining(self, today: date) -> int:
        return max(0, self.limit - self._count(today))

    def use(self, today: date) -> None:
        count = self._count(today)
        if count >= self.limit:
            raise CapReached(f"Daily limit of {self.limit} shorts reached. Try again tomorrow.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"date": today.isoformat(), "count": count + 1}))
