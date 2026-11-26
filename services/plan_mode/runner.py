"""Plan-mode runner: production.json -> assets -> TTS -> MP4. No LLM calls.

Reuses the existing downstream stages unchanged:
  * services.ai.media.providers.{wikimedia,pexels}  asset search
  * services.ai.media.downloader.MediaDownloader    asset download / local files
  * services.audio.generate_audio / get_audio_duration   TTS (Kokoro -> gTTS)
  * services.renderer.render_video                  Ken Burns / clip / xfade / subtitles / mux

This is the same hand-off the studio pipeline performs in
``_render_studio_video`` (image_paths + ai_clip_paths + audio + subtitle_lines),
minus every LLM agent stage in front of it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from config import OUTPUT_DIR
from services.plan_mode.schema import ProductionPlan, Scene, VisualKind, split_durations

logger = logging.getLogger(__name__)

# render_video() hard-codes 0.4s xfade between scenes (see renderer.render_video).
TRANSITION_SECONDS = 0.4
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


@dataclass
class ResolvedScene:
    path: Path
    is_video: bool
    source: str                       # provider name, "url", "text_card" or "fallback"
    section: str
    scene: Scene
    credit: dict = field(default_factory=dict)
    warning: str | None = None


@dataclass
class PlanRunResult:
    video_path: Path
    duration_seconds: float
    warnings: list[str]
    credits_path: Path


# ── Assets ───────────────────────────────────────────────────────────────────

def _intent(query: str, want_video: bool):
    from services.ai.media.asset_types import AssetKind
    from services.ai.media.visual_intent import SubjectType, VisualIntent

    return VisualIntent(
        subject=query,
        subject_type=SubjectType.OBJECT,
        action="",
        search_keywords=[query],  # concise_search_query uses these verbatim
        preferred_asset_kind=AssetKind.STOCK_VIDEO if want_video else AssetKind.STOCK_IMAGE,
    )


def _pick(candidates, used_urls: set[str], want_video: bool):
    """First unused candidate; for images prefer >=1280px wide (old scans look bad)."""
    fresh = [c for c in candidates if c.url not in used_urls]
    if not want_video:
        big = [c for c in fresh if (c.width or 0) >= 1280]
        fresh = big or fresh
    return fresh[0] if fresh else None


def _looks_like_video(url: str) -> bool:
    return Path(url.split("?")[0]).suffix.lower() in VIDEO_SUFFIXES


def _image_ok(path: Path) -> bool:
    from PIL import Image

    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def _text_card(text: str, dest: Path, width: int, height: int) -> Path:
    from services.renderer import create_fallback_frame

    create_fallback_frame(text or "…", dest, width, height)
    return dest


async def _download(asset):
    from services.ai.media.downloader import MediaDownloader

    return (await asyncio.to_thread(MediaDownloader().download, asset)).local_path


async def resolve_scene(
    scene: Scene,
    *,
    section_title: str,
    index: int,
    work_dir: Path,
    plan_dir: Path,
    width: int,
    height: int,
    used_urls: set[str],
) -> ResolvedScene:
    """Turn one scene spec into a local file. Never raises: failures become a text card."""
    card_path = work_dir / f"card_{index:03d}.png"

    if scene.kind is VisualKind.TEXT_CARD:
        _text_card(scene.text or "", card_path, width, height)
        return ResolvedScene(card_path, False, "text_card", section_title, scene)

    try:
        from services.ai.media.asset import MediaAsset
        from services.ai.media.asset_types import AssetKind

        if scene.kind is VisualKind.URL:
            url = scene.url or ""
            if not url.startswith(("http://", "https://", "file://")):
                local = Path(url).expanduser()
                url = str(local if local.is_absolute() else (plan_dir / local).resolve())
            is_video = _looks_like_video(url)
            asset = MediaAsset(
                url=url,
                kind=AssetKind.STOCK_VIDEO if is_video else AssetKind.STOCK_IMAGE,
                provider="url",
                provider_id=url,
                title=scene.caption or "",
            )
            credit = {"provider": "url", "url": scene.url}
        else:
            want_video = scene.kind is VisualKind.PEXELS_VIDEO
            if scene.kind is VisualKind.WIKIMEDIA:
                from services.ai.media.providers.wikimedia import WikimediaProvider as Provider
            else:
                from services.ai.media.providers.pexels import PexelsProvider as Provider
            provider = Provider()
            if not provider.is_configured():
                raise RuntimeError("PEXELS_API_KEY is not set")
            candidates = await provider.search(_intent(scene.query or "", want_video), limit=8)
            asset = _pick(candidates, used_urls, want_video)
            if asset is None:
                raise RuntimeError(f"no usable results for query '{scene.query}'")
            is_video = want_video
            credit = {
                "provider": asset.provider,
                "url": asset.url,
                "title": asset.title,
                "author": asset.author,
                "licensing": asset.licensing,
            }

        path = await _download(asset)
        if not is_video and not _image_ok(path):
            raise RuntimeError(f"downloaded file is not a valid image: {path.name}")
        used_urls.add(asset.url)
        return ResolvedScene(path, is_video, asset.provider, section_title, scene, credit)

    except Exception as exc:  # noqa: BLE001 - any failure must degrade to a card, not abort the render
        msg = f"scene {index} ({scene.kind.value}) fell back to a text card: {exc}"
        logger.warning(msg)
        _text_card(scene.fallback_text or section_title, card_path, width, height)
        return ResolvedScene(card_path, False, "fallback", section_title, scene, warning=msg)


# ── Audio ────────────────────────────────────────────────────────────────────

def _concat_audio(parts: list[Path], dest: Path) -> Path:
    """Join per-section narration (mixed wav/mp3 is fine) into one mono 44.1 kHz wav."""
    if len(parts) == 1:
        return parts[0]
    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", str(p)]
    norm = "".join(
        f"[{i}:a]aresample=44100,aformat=channel_layouts=mono[a{i}];" for i in range(len(parts))
    )
    joined = "".join(f"[a{i}]" for i in range(len(parts)))
    cmd += ["-filter_complex", f"{norm}{joined}concat=n={len(parts)}:v=0:a=1[out]",
            "-map", "[out]", str(dest)]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"audio concat failed: {res.stderr.decode()[-400:]}")
    return dest


def build_subtitle_lines(
    narration: str, start: float, duration: float, words_per_card: int = 7
) -> list[tuple[str, float, float]]:
    """Timed subtitle cards for one section, offset to its place in the full audio.

    Cards are sized by character count (same approach as the studio pipeline's
    _build_subtitle_lines) so short and long cards don't drift from the voice.
    """
    words = narration.split()
    if not words or duration <= 0:
        return []
    cards = [" ".join(words[i:i + words_per_card]) for i in range(0, len(words), words_per_card)]
    weights = [max(1, len(c)) for c in cards]
    total = sum(weights)
    out, cursor = [], start
    for text, w in zip(cards, weights):
        d = duration * w / total
        out.append((text, round(cursor, 3), round(cursor + d, 3)))
        cursor += d
    return out


def scene_clip_durations(section_seconds: list[float], section_weights: list[list[float]]) -> list[float]:
    """Per-scene clip lengths to hand to render_video, flattened across sections.

    render_video overlaps consecutive clips by TRANSITION_SECONDS (xfade). Adding
    that overlap to every clip but the last makes each scene *start* exactly where
    its narration share starts and the video end exactly at the audio end.
    """
    shares = [d for secs, ws in zip(section_seconds, section_weights) for d in split_durations(secs, ws)]
    return [round(s + (TRANSITION_SECONDS if i < len(shares) - 1 else 0.0), 3) for i, s in enumerate(shares)]


# ── Orchestration ────────────────────────────────────────────────────────────

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30] or "plan"


async def run_plan(plan: ProductionPlan, out_path: Path, plan_dir: Path | None = None) -> PlanRunResult:
    from services.audio import generate_audio, get_audio_duration
    from services.renderer import dimensions_for_aspect_ratio, render_video

    plan_dir = plan_dir or Path.cwd()
    run_id = f"plan_{_slug(plan.title)}_{uuid.uuid4().hex[:6]}"
    work_dir = OUTPUT_DIR / run_id
    work_dir.mkdir(parents=True, exist_ok=True)
    width, height = dimensions_for_aspect_ratio(plan.aspect_ratio)
    warnings: list[str] = []

    # 1. Assets (per scene, in order)
    logger.info("[plan] resolving %d scenes", plan.scene_count)
    resolved: list[ResolvedScene] = []
    used_urls: set[str] = set()
    for section in plan.sections:
        for scene in section.scenes:
            rs = await resolve_scene(
                scene, section_title=section.title, index=len(resolved), work_dir=work_dir,
                plan_dir=plan_dir, width=width, height=height, used_urls=used_urls,
            )
            if rs.warning:
                warnings.append(rs.warning)
            resolved.append(rs)

    music_path = None
    if plan.music:
        try:
            from services.ai.media.asset import MediaAsset
            from services.ai.media.asset_types import AssetKind

            m = plan.music
            if not m.startswith(("http://", "https://", "file://")):
                p = Path(m).expanduser()
                m = str(p if p.is_absolute() else (plan_dir / p).resolve())
            music_path = await _download(
                MediaAsset(url=m, kind=AssetKind.LOCAL, provider="music", provider_id=m)
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"music skipped: {exc}")

    # 2. Narration, one TTS call per section so each section's real duration is known
    section_audio: list[Path] = []
    section_secs: list[float] = []
    for i, section in enumerate(plan.sections):
        logger.info("[plan] TTS section %d/%d: %s", i + 1, len(plan.sections), section.title)
        path = await generate_audio(section.narration, job_id=f"{run_id}_s{i:02d}", voice_id=plan.voice)
        section_audio.append(path)
        section_secs.append(get_audio_duration(path))
    audio_path = _concat_audio(section_audio, work_dir / "narration.wav")
    total = sum(section_secs)

    # 3. Timeline + subtitles
    durations = scene_clip_durations(section_secs, [[sc.duration_weight for sc in s.scenes] for s in plan.sections])
    subtitle_lines: list[tuple[str, float, float]] = []
    if plan.subtitles:
        cursor = 0.0
        for section, secs in zip(plan.sections, section_secs):
            subtitle_lines += build_subtitle_lines(section.narration, cursor, secs)
            cursor += secs

    # 4. Render
    video = await render_video(
        audio_path=audio_path,
        image_paths=[(r.path, d) for r, d in zip(resolved, durations)],
        ai_clip_paths=[r.path if r.is_video else None for r in resolved],
        script={"hook": plan.hook, "cta": plan.cta},
        job_id=run_id,
        actual_duration=total,
        subtitle_lines=subtitle_lines,
        bgm_path=music_path,
        aspect_ratio=plan.aspect_ratio,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(video), str(out_path))

    # 5. Sidecar: YouTube metadata + per-scene credits (Wikimedia/Pexels attribution)
    credits_path = out_path.with_suffix(".credits.json")
    credits_path.write_text(json.dumps({
        "title": plan.title,
        "description": plan.description,
        "tags": plan.tags,
        "duration_seconds": round(total, 2),
        "warnings": warnings,
        "scenes": [
            {"section": r.section, "kind": r.scene.kind.value, "source": r.source,
             "caption": r.scene.caption, **r.credit}
            for r in resolved
        ],
    }, indent=2), encoding="utf-8")
    return PlanRunResult(out_path, total, warnings, credits_path)
