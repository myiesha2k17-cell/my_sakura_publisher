import json
import subprocess
from datetime import date, timedelta

import pytest

from shorts.providers.fakes import FakeTTS
from shorts.settings import CapReached, DailyCap, Settings


def test_defaults():
    s = Settings.from_sources({}, None)
    assert s.claude_model == "claude-opus-5-5"
    assert s.daily_cap == 10
    assert s.password is None


def test_secrets_override_env():
    s = Settings.from_sources({"SHORTS_PASSWORD": "env", "SHORTS_DAILY_CAP": "3"},
                              {"SHORTS_PASSWORD": "secret"})
    assert s.password == "secret"
    assert s.daily_cap == 3


def test_missing_keys():
    s = Settings.from_sources({}, None)
    assert s.missing_for_script() == ["ANTHROPIC_API_KEY"]
    assert s.missing_for_render() == ["ELEVENLABS_API_KEY"]
    full = Settings.from_sources({"ANTHROPIC_API_KEY": "a", "ELEVENLABS_API_KEY": "e"}, None)
    assert full.missing_for_script() == [] and full.missing_for_render() == []


def test_daily_cap(tmp_path):
    cap = DailyCap(tmp_path / "cap.json", limit=2)
    today = date(2026, 11, 24)
    cap.use(today)
    cap.use(today)
    assert cap.remaining(today) == 0
    with pytest.raises(CapReached):
        cap.use(today)
    assert cap.remaining(today + timedelta(days=1)) == 2


def _ffprobe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def test_fake_tts_duration(tmp_path):
    text = "one two three four five six seven eight nine ten"
    result = FakeTTS(words_per_sec=2.5).synthesize(text, "voice", tmp_path / "v.m4a")
    assert abs(_ffprobe_duration(result.audio_path) - 4.0) < 0.1
    assert abs(result.duration - 4.0) < 0.1
    assert len(result.words) == 10
    starts = [w.start for w in result.words]
    assert starts == sorted(starts) and len(set(starts)) == 10
