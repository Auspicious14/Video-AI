"""Tests for plan-file mode. No network, no API keys, no real TTS.

Run: python3 -m pytest -q tests/test_plan_mode.py
"""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import sys
import wave
from pathlib import Path
from unittest import mock

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.plan_mode.schema import (  # noqa: E402
    ProductionPlan,
    VisualKind,
    estimate_duration,
    format_summary,
    load_plan,
    split_durations,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "production.example.json"


def _plan_dict() -> dict:
    return {
        "title": "T",
        "sections": [
            {
                "title": "S1",
                "narration": "one two three four five six",
                "scenes": [
                    {"kind": "text_card", "text": "hello", "duration_weight": 1},
                    {"kind": "wikimedia", "query": "cat", "duration_weight": 3},
                ],
            },
            {
                "title": "S2",
                "narration": "seven eight nine ten",
                "scenes": [{"kind": "pexels_video", "query": "sea"}],
            },
        ],
    }


@pytest.fixture(autouse=True)
def _no_network():
    """Fail any test that tries to open a socket."""
    with mock.patch("socket.socket.connect", side_effect=AssertionError("network access in test")):
        yield


# ── Schema ───────────────────────────────────────────────────────────────────

def test_example_plan_is_valid():
    plan = load_plan(EXAMPLE)
    assert 2 <= len(plan.sections) <= 3
    assert 60 <= plan.estimated_duration_seconds <= 90
    assert plan.aspect_ratio == "16:9"


def test_defaults_and_counts():
    plan = ProductionPlan.model_validate(_plan_dict())
    assert plan.aspect_ratio == "16:9"
    assert plan.voice is None and plan.music is None
    assert plan.word_count == 10
    assert plan.scene_count == 3
    assert plan.estimated_duration_seconds == pytest.approx(estimate_duration(10))
    assert plan.sections[0].scenes[0].kind is VisualKind.TEXT_CARD


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("title"),
        lambda d: d.update(sections=[]),
        lambda d: d.update(aspect_ratio="4:3"),
        lambda d: d.update(bogus_field=1),
        lambda d: d["sections"][0].update(narration="   "),
        lambda d: d["sections"][0].update(scenes=[]),
        lambda d: d["sections"][0]["scenes"][0].update(kind="youtube"),
        lambda d: d["sections"][0]["scenes"][1].pop("query"),        # wikimedia needs query
        lambda d: d["sections"][1]["scenes"][0].update(query=" "),   # blank query
        lambda d: d["sections"][0]["scenes"][0].pop("text"),         # text_card needs text
        lambda d: d["sections"][0]["scenes"][0].update(kind="url", text=None),  # url needs url
        lambda d: d["sections"][0]["scenes"][0].update(duration_weight=0),
        lambda d: d["sections"][0]["scenes"][0].update(duration_weight=-1),
    ],
)
def test_bad_plans_rejected(mutate):
    data = copy.deepcopy(_plan_dict())
    mutate(data)
    with pytest.raises(ValidationError):
        ProductionPlan.model_validate(data)


def test_load_plan_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_plan(bad)


def test_summary_mentions_env_and_words():
    plan = ProductionPlan.model_validate(_plan_dict())
    text = format_summary(plan)
    assert "Words:      10" in text
    assert "PEXELS_API_KEY" in text
    no_pexels = _plan_dict()
    no_pexels["sections"][1]["scenes"][0] = {"kind": "text_card", "text": "x"}
    assert "Env needed: none" in format_summary(ProductionPlan.model_validate(no_pexels))


# ── Duration splitting ───────────────────────────────────────────────────────

def test_split_durations_proportional_and_exact():
    parts = split_durations(10.0, [1, 3])
    assert parts == pytest.approx([2.5, 7.5])
    assert sum(parts) == pytest.approx(10.0)


def test_split_durations_sum_exact_with_awkward_weights():
    parts = split_durations(7.0, [1, 1, 1])
    assert sum(parts) == pytest.approx(7.0, abs=1e-9)
    assert split_durations(5.0, [2]) == [5.0]
    assert split_durations(5.0, []) == []


def test_split_durations_rejects_nonpositive():
    with pytest.raises(ValueError):
        split_durations(5.0, [1, 0])


def test_scene_clip_durations_account_for_xfade_overlap():
    from services.plan_mode.runner import TRANSITION_SECONDS, scene_clip_durations

    # two sections (6s: 1:2, 4s: single scene) -> shares 2, 4, 4
    d = scene_clip_durations([6.0, 4.0], [[1, 2], [1]])
    t = TRANSITION_SECONDS
    assert d == pytest.approx([2 + t, 4 + t, 4])
    # post-xfade timeline length equals the narration length
    assert sum(d) - (len(d) - 1) * t == pytest.approx(10.0)


def test_subtitle_lines_cover_section_window():
    from services.plan_mode.runner import build_subtitle_lines

    lines = build_subtitle_lines(" ".join(["w"] * 20), start=5.0, duration=10.0)
    assert lines[0][1] == pytest.approx(5.0)
    assert lines[-1][2] == pytest.approx(15.0)
    assert build_subtitle_lines("", 0, 5) == []


# ── Runner (everything external mocked) ──────────────────────────────────────

def _silent_wav(path: Path, seconds: float) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * int(22050 * seconds))
    return path


@pytest.fixture
def isolated_outputs(tmp_path, monkeypatch):
    import services.plan_mode.runner as runner

    monkeypatch.setattr(runner, "OUTPUT_DIR", tmp_path / "out")
    return tmp_path


def _llm_tripwires():
    """Patch every public entry into the LLM layer so any call fails the test."""
    boom = mock.Mock(side_effect=AssertionError("LLM layer was called in plan mode"))
    import services.ai.client as client
    import services.ai.providers as providers

    return [
        mock.patch.object(client, "generate_json", boom),
        mock.patch.object(client, "generate_text", boom),
        mock.patch.object(client, "generate_text_with_metadata", boom),
        mock.patch.object(client, "_call_provider", boom),
        mock.patch.object(client, "_run_with_failover", boom),
        mock.patch.object(providers, "get_enabled_providers", boom),
        mock.patch.object(client, "get_enabled_providers", boom),
    ], boom


def test_run_plan_never_calls_llm_and_wires_stages(isolated_outputs, monkeypatch):
    import services.audio as audio
    import services.plan_mode.runner as runner
    import services.renderer as renderer

    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY", "PEXELS_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    plan = ProductionPlan.model_validate(_plan_dict())
    out = isolated_outputs / "final.mp4"
    tts_calls: list[tuple[str, str | None]] = []
    render_kwargs: dict = {}

    async def fake_tts(narration, job_id, voice_id=None, preferred_provider=None):
        tts_calls.append((narration, voice_id))
        return _silent_wav(isolated_outputs / f"{job_id}.wav", 6.0 if len(tts_calls) == 1 else 4.0)

    async def fake_render(**kwargs):
        render_kwargs.update(kwargs)
        p = isolated_outputs / "rendered.mp4"
        p.write_bytes(b"mp4")
        return p

    # wikimedia returns nothing / pexels has no key -> scenes degrade to text cards
    async def no_results(self, intent, limit=5):
        return []

    from services.ai.media.providers.wikimedia import WikimediaProvider
    monkeypatch.setattr(WikimediaProvider, "search", no_results)
    tripwires, boom = _llm_tripwires()
    for p in tripwires:
        p.start()
    try:
        with mock.patch.object(audio, "generate_audio", fake_tts), \
             mock.patch.object(renderer, "render_video", fake_render), \
             mock.patch.object(runner, "_concat_audio", lambda parts, dest: parts[0]):
            result = asyncio.run(runner.run_plan(plan, out, plan_dir=isolated_outputs))
    finally:
        for p in tripwires:
            p.stop()

    boom.assert_not_called()
    assert out.read_bytes() == b"mp4"
    # one TTS call per section, narration verbatim, voice passed through
    assert [t[0] for t in tts_calls] == [s.narration for s in plan.sections]
    # 3 scenes -> 3 timeline entries; 2 fell back (wikimedia + pexels w/o key)
    assert len(render_kwargs["image_paths"]) == 3
    assert len(result.warnings) == 2
    assert all(Path(p).exists() for p, _ in render_kwargs["image_paths"])
    assert render_kwargs["aspect_ratio"] == "16:9"
    assert render_kwargs["actual_duration"] == pytest.approx(10.0)
    # xfade-compensated clip lengths: shares 1.5, 4.5, 4 (+0.4 on all but the last)
    assert [d for _, d in render_kwargs["image_paths"]] == pytest.approx([1.9, 4.9, 4.0])
    sidecar = json.loads(result.credits_path.read_text())
    assert sidecar["title"] == "T" and len(sidecar["scenes"]) == 3


def test_resolve_scene_uses_provider_and_downloader_when_available(isolated_outputs):
    import services.plan_mode.runner as runner
    from services.ai.media.asset import MediaAsset
    from services.ai.media.asset_types import AssetKind
    from services.ai.media.providers.wikimedia import WikimediaProvider
    from PIL import Image

    img = isolated_outputs / "dl.jpg"
    Image.new("RGB", (64, 64), "red").save(img)

    async def fake_search(self, intent, limit=5):
        assert intent.concise_search_query == "red cat"  # query passed through verbatim
        return [
            MediaAsset(url="http://x/small.jpg", kind=AssetKind.STOCK_IMAGE, provider="wikimedia",
                       provider_id="a", width=400, height=300),
            MediaAsset(url="http://x/big.jpg", kind=AssetKind.STOCK_IMAGE, provider="wikimedia",
                       provider_id="b", width=3000, height=2000, author="Someone"),
        ]

    async def fake_download(asset):
        fake_download.url = asset.url
        return img

    from services.plan_mode.schema import Scene

    work = isolated_outputs / "w"
    work.mkdir()
    used: set[str] = set()
    with mock.patch.object(WikimediaProvider, "search", fake_search), \
         mock.patch.object(runner, "_download", fake_download):
        rs = asyncio.run(runner.resolve_scene(
            Scene(kind="wikimedia", query="red cat"), section_title="S", index=0,
            work_dir=work, plan_dir=isolated_outputs, width=320, height=180, used_urls=used))
    assert rs.source == "wikimedia" and rs.warning is None and not rs.is_video
    assert fake_download.url == "http://x/big.jpg"  # prefers the large image
    assert used == {"http://x/big.jpg"}
    assert rs.credit["author"] == "Someone"


def test_url_scene_local_file_and_video_detection(isolated_outputs):
    import services.plan_mode.runner as runner
    from services.plan_mode.schema import Scene
    from PIL import Image

    img = isolated_outputs / "pic.png"
    Image.new("RGB", (800, 600), "blue").save(img)
    vid = isolated_outputs / "clip.mp4"
    vid.write_bytes(b"0" * 5000)
    work = isolated_outputs / "w"
    work.mkdir()
    kw = dict(section_title="S", index=0, work_dir=work, plan_dir=isolated_outputs,
              width=320, height=180, used_urls=set())

    rs = asyncio.run(runner.resolve_scene(Scene(kind="url", url="pic.png"), **kw))  # relative to plan dir
    assert rs.path == img and not rs.is_video and rs.warning is None
    rs = asyncio.run(runner.resolve_scene(Scene(kind="url", url=str(vid)), **kw))
    assert rs.path == vid and rs.is_video
    rs = asyncio.run(runner.resolve_scene(Scene(kind="url", url="missing.png", text="fallback words"), **kw))
    assert rs.source == "fallback" and rs.warning and rs.path.exists()


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_dry_run_makes_no_heavy_imports_or_network(capsys):
    import generate_from_plan

    with mock.patch("socket.socket", side_effect=AssertionError("network used in dry run")):
        rc = generate_from_plan.main([str(EXAMPLE), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Est. time" in out and "Dry run OK" in out


def test_cli_dry_run_rejects_bad_plan(tmp_path, capsys):
    import generate_from_plan

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"title": "x", "sections": [{"title": "a", "narration": "b", "scenes": []}]}))
    assert generate_from_plan.main([str(bad), "--dry-run"]) == 2
    assert "Invalid plan" in capsys.readouterr().err


# ── Real ffmpeg smoke test (offline: text cards + synthetic narration) ───────

@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
def test_end_to_end_offline_render_with_fake_tts(isolated_outputs):
    import services.audio as audio
    import services.plan_mode.runner as runner

    plan = ProductionPlan.model_validate({
        "title": "Smoke", "aspect_ratio": "1:1", "hook": "Hello",
        "sections": [
            {"title": "A", "narration": "alpha beta gamma delta",
             "scenes": [{"kind": "text_card", "text": "One"}, {"kind": "text_card", "text": "Two"}]},
            {"title": "B", "narration": "epsilon zeta",
             "scenes": [{"kind": "text_card", "text": "Three"}]},
        ],
    })
    lengths = iter([3.0, 2.5])

    async def fake_tts(narration, job_id, voice_id=None, preferred_provider=None):
        return _silent_wav(isolated_outputs / f"{job_id}.wav", next(lengths))

    out = isolated_outputs / "smoke.mp4"
    # point the real renderer's output dir at tmp too
    import services.renderer as renderer
    with mock.patch.object(audio, "generate_audio", fake_tts), \
         mock.patch.object(renderer, "OUTPUT_DIR", isolated_outputs / "out"):
        (isolated_outputs / "out").mkdir(exist_ok=True)
        result = asyncio.run(runner.run_plan(plan, out, plan_dir=isolated_outputs))
    assert out.exists() and out.stat().st_size > 1000
    import subprocess
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True).stdout)
    assert dur == pytest.approx(5.5, abs=0.6)
    assert result.credits_path.exists()
