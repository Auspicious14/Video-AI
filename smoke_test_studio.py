"""
smoke_test_studio.py — exercises your REAL YouTube Studio pipeline.

This is not a rewrite. It imports and calls the exact function your
/generate/youtube-studio route calls:
    services.ai.studio.run_youtube_studio_production

Run from your project root (same place you'd run `uvicorn main:app`):

    python smoke_test_studio.py --topic "The Rise of Netflix" --duration 90
    python smoke_test_studio.py --topic "The Rise of Netflix" --duration 90 --render

Without --render it stops after the production package (script, visuals,
audio, packaging) — fast, and isolates the AI orchestration from FFmpeg.
With --render it also produces the final MP4.
"""

from __future__ import annotations

import argparse
import asyncio
import time
import uuid

from dotenv import load_dotenv

load_dotenv()  # must happen before importing anything that reads os.getenv() at import time

import store
from models import YouTubeStudioRequest
from services.ai.studio import run_youtube_studio_production


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--duration", type=int, default=90)
    parser.add_argument(
        "--render",
        action="store_true",
        help="Also render the final MP4, not just the production package",
    )
    args = parser.parse_args()

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, video_type="youtube_studio")

    req = YouTubeStudioRequest(
        user_email="smoketest@local",
        topic=args.topic,
        custom_duration=args.duration,
        generate_audio=True,
        generate_images=True,
        render_video=args.render,
    )

    print(
        f"[smoke test] job_id={job_id} topic={args.topic!r} "
        f"duration={args.duration}s render={args.render}\n"
    )
    t0 = time.monotonic()

    await run_youtube_studio_production(job_id, req)

    elapsed = time.monotonic() - t0
    job = store.get_job(job_id) or {}

    print(f"\n[smoke test] finished in {elapsed:.1f}s")
    print(f"  status:   {job.get('status')}")
    print(f"  detail:   {job.get('status_detail')}")
    print(f"  quality:  {job.get('quality_score')}")
    print(f"  warnings: {job.get('warnings')}")
    print(f"  package:  {job.get('package_url')}")
    print(f"  video:    {job.get('video_url')}")
    if job.get("error"):
        print(f"  ERROR:    {job['error']}")


if __name__ == "__main__":
    asyncio.run(main())