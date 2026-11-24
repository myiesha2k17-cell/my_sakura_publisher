import subprocess

import pytest
from PIL import Image

from shorts.captions import write_ass
from shorts.models import WordTiming
from shorts.providers.fakes import FakeTTS
from shorts.render import RenderScene, probe, render_video


@pytest.fixture
def inputs(tmp_path):
    scenes = []
    for i, color in enumerate(["#2B2560", "#F2A93B", "#3E5A6B"]):
        p = tmp_path / f"s{i}.png"
        Image.new("RGB", (1080, 1920), color).save(p)
        scenes.append(RenderScene(image=p, seconds=3.0))
    voice = FakeTTS(words_per_sec=2.5).synthesize(" ".join(["word"] * 20), "v", tmp_path / "voice.m4a")
    ass = write_ass([WordTiming(word="hello there", start=0.2, end=1.5)], tmp_path / "c.ass",
                    font="DejaVuSans-Bold", primary="#FFFFFF", outline="#000000")
    end = tmp_path / "end.png"
    Image.new("RGB", (1080, 1920), "#111111").save(end)
    return scenes, voice.audio_path, ass, end


def test_render_specs(tmp_path, inputs):
    scenes, voice, ass, end = inputs
    out = render_video(scenes, voice, ass, tmp_path / "out.mp4", end_card=end, end_seconds=2.5)
    info = probe(out)
    assert (info["width"], info["height"], info["fps"]) == (1080, 1920, 30)
    assert abs(info["duration"] - 11.5) <= 0.3
    assert info["has_audio"]


def test_render_with_music_ducked(tmp_path, inputs):
    scenes, voice, ass, end = inputs
    music = tmp_path / "music.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=30",
                    "-c:a", "aac", str(music)], check=True)
    out = render_video(scenes, voice, ass, tmp_path / "out.mp4", music=music, end_card=end, end_seconds=2.5)
    info = probe(out)
    assert info["audio_streams"] == 1
    assert abs(info["duration"] - 11.5) <= 0.3


def test_render_odd_image(tmp_path, inputs):
    _, voice, ass, _ = inputs
    odd = tmp_path / "odd.png"
    Image.new("RGB", (200, 100), "#884488").save(odd)
    out = render_video([RenderScene(image=odd, seconds=2.0)], voice, ass, tmp_path / "out.mp4")
    info = probe(out)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert abs(info["duration"] - 2.0) <= 0.3
