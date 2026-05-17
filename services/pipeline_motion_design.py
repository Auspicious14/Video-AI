"""
services/pipeline_motion_design.py

Pipeline for: Motion Design (Remotion-based)

Flow:
  1. Gemini generates a structured DesignBrief JSON
     - from topic (text prompt) → generate_brief_from_topic()
     - from flyer image         → generate_brief_from_flyer()
  2. Brief is written to a temp .json file
  3. `remotion render <CompositionId> --props=<json_file> --output=<mp4>` is called
     as a subprocess with a generous timeout
  4. On success → job marked done, video_url set
  5. On any failure → job marked failed with a clear error message

Remotion must be installed globally: npm install -g remotion @remotion/cli
The remotion-templates project must be present and npm-installed at:
  <project_root>/remotion-templates/
"""

import asyncio
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from models import MotionDesignRequest
import store
from config import OUTPUT_DIR
from services.motion_brief import (
    generate_brief_from_topic,
    generate_brief_from_flyer,
    brief_to_composition_id,
)

# ── Paths ──────────────────────────────────────────────────────────────────────

# Root of the repo — two levels up from this file (services/ → backend/ → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Where the remotion-templates project lives
REMOTION_PROJECT = _PROJECT_ROOT / "remotion-templates"

# Timeout for the entire Remotion render subprocess (seconds)
REMOTION_TIMEOUT = 300  # 5 minutes — generous for first-run Chrome download


# ── Main entry point ───────────────────────────────────────────────────────────

async def run_motion_design_pipeline(
    job_id: str,
    req: MotionDesignRequest,
    flyer_image_path: Optional[Path] = None,
) -> None:
    """
    Full motion design pipeline.

    Args:
        job_id:            The job identifier (already created in store).
        req:               The MotionDesignRequest from the API.
        flyer_image_path:  If set, Gemini reads the flyer image instead of topic.
    """
    try:
        # ── Step 1: Generate design brief ─────────────────────────────────────
        store.update_job(
            job_id,
            status="generating_brief",
            status_detail="Gemini is designing your motion video…",
            progress=10,
        )

        aspect_ratio = getattr(req, "aspect_ratio", "9:16") or "9:16"

        if flyer_image_path and flyer_image_path.exists():
            brief = await generate_brief_from_flyer(
                flyer_image_path=flyer_image_path,
                style=req.style,
                aspect_ratio=aspect_ratio,
                duration=req.duration,
            )
        else:
            brief = await generate_brief_from_topic(
                topic=req.topic,
                style=req.style,
                aspect_ratio=aspect_ratio,
                duration=req.duration,
                brand_name=req.brand_name,
                brand_color=req.brand_color,
            )

        composition_id = brief_to_composition_id(brief)

        store.update_job(
            job_id,
            status="rendering",
            status_detail=f"Remotion is rendering {brief['style']} template…",
            progress=35,
        )

        # ── Step 2: Write brief to temp file ──────────────────────────────────
        output_path = OUTPUT_DIR / f"{job_id}_motion.mp4"

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            prefix=f"brief_{job_id}_",
        ) as tmp:
            # Remotion --props expects the top-level props object for the composition.
            # Our compositions accept { brief: DesignBrief }, so we wrap it.
            json.dump({"brief": brief}, tmp, ensure_ascii=False, indent=2)
            props_path = tmp.name

        # ── Step 3: Run Remotion render ────────────────────────────────────────
        try:
            await _run_remotion(
                composition_id=composition_id,
                props_path=props_path,
                output_path=output_path,
                job_id=job_id,
            )
        finally:
            # Always clean up the temp props file
            try:
                os.unlink(props_path)
            except OSError:
                pass

        # ── Step 4: Verify output ──────────────────────────────────────────────
        if not output_path.exists() or output_path.stat().st_size < 10_000:
            raise RuntimeError(
                f"Remotion render completed but output file is missing or too small: {output_path}"
            )

        # ── Step 5: Mark done ──────────────────────────────────────────────────
        video_url = f"/outputs/{output_path.name}"
        caption = _build_caption(brief)
        cta_text = brief.get("cta", "")

        store.update_job(
            job_id,
            status="done",
            status_detail="Motion design video ready!",
            progress=100,
            video_url=video_url,
            caption=caption,
            cta=cta_text,
        )

    except asyncio.CancelledError:
        store.update_job(job_id, status="failed", error="Pipeline was cancelled.")
        raise

    except Exception as exc:
        store.update_job(
            job_id,
            status="failed",
            error=f"Motion design pipeline failed: {exc}",
        )
        raise


# ── Remotion subprocess ────────────────────────────────────────────────────────

async def _run_remotion(
    composition_id: str,
    props_path: str,
    output_path: Path,
    job_id: str,
) -> None:
    """
    Calls:
      remotion render <entry> <compositionId> --props=<path> --output=<path>
        --log=verbose --concurrency=1

    Runs in a thread executor so it doesn't block the event loop.
    """
    entry_point = str(REMOTION_PROJECT / "src" / "index.ts")

    cmd = [
        "remotion",
        "render",
        entry_point,
        composition_id,
        f"--props={props_path}",
        f"--output={output_path}",
        "--log=verbose",
        "--concurrency=1",         # single thread — safer on VPS
        "--overwrite",
    ]

    loop = asyncio.get_running_loop()

    def _run() -> tuple[int, str, str]:
        """Blocking call — runs in thread pool."""
        start = time.time()
        result = subprocess.run(
            cmd,
            cwd=str(REMOTION_PROJECT),
            capture_output=True,
            text=True,
            timeout=REMOTION_TIMEOUT,
        )
        elapsed = time.time() - start
        return result.returncode, result.stdout, result.stderr, elapsed

    # Progress ping while Remotion renders
    async def _ping_progress():
        progress = 35
        while progress < 90:
            await asyncio.sleep(8)
            progress = min(progress + 8, 88)
            store.update_job(
                job_id,
                progress=progress,
                status_detail=f"Rendering… ({progress}%)",
            )

    # Run render + progress pings concurrently
    render_task   = loop.run_in_executor(None, _run)
    progress_task = asyncio.ensure_future(_ping_progress())

    try:
        returncode, stdout, stderr, elapsed = await asyncio.wait_for(
            asyncio.shield(render_task),
            timeout=REMOTION_TIMEOUT + 10,
        )
    finally:
        progress_task.cancel()

    if returncode != 0:
        # Surface the most useful part of the error
        error_detail = _extract_remotion_error(stdout, stderr)
        raise RuntimeError(
            f"Remotion exited with code {returncode} after {elapsed:.1f}s.\n{error_detail}"
        )


def _extract_remotion_error(stdout: str, stderr: str) -> str:
    """Extract the most useful error lines from Remotion's verbose output."""
    combined = (stderr + "\n" + stdout).strip()
    lines = combined.splitlines()

    # Look for lines with Error, error, TypeError, etc.
    error_lines = [
        line for line in lines
        if any(kw in line for kw in ["Error", "error", "TypeError", "Cannot", "failed", "ENOENT"])
    ]

    if error_lines:
        return "\n".join(error_lines[-10:])   # last 10 error lines

    # Fallback: last 15 lines of output
    return "\n".join(lines[-15:])


# ── Caption builder ────────────────────────────────────────────────────────────

def _build_caption(brief: dict) -> str:
    """Build a social-ready caption from the brief."""
    title    = brief.get("title", "")
    subtitle = brief.get("subtitle", "")
    brand    = brief.get("brandName", "")
    cta      = brief.get("cta", "")

    parts = [title]
    if subtitle:
        parts.append(subtitle)
    if brand:
        parts.append(f"\n\n— {brand}")
    if cta:
        parts.append(f"\n\n{cta} ↗")

    return " ".join(parts).strip()