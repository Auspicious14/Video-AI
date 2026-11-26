"""Plan-file mode CLI: render a documentary from production.json with NO LLM calls.

    python generate_from_plan.py path/to/production.json [--out outputs/x.mp4] [--dry-run]

See PLAN_MODE.md.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

# Only the dependency-light schema module is imported at top level, so --dry-run
# works with no ffmpeg / TTS / network / API keys.
from services.plan_mode.schema import format_summary, load_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a documentary from a production plan (no LLM).")
    parser.add_argument("plan", type=Path, help="path to production.json")
    parser.add_argument("--out", type=Path, default=None, help="output mp4 (default: outputs/<plan-name>.mp4)")
    parser.add_argument("--dry-run", action="store_true", help="validate and summarise only; no network")
    args = parser.parse_args(argv)

    try:
        plan = load_plan(args.plan)
    except (ValidationError, ValueError, OSError) as exc:
        print(f"Invalid plan: {exc}", file=sys.stderr)
        return 2

    print(format_summary(plan))
    if args.dry_run:
        print("\nDry run OK - plan is valid.")
        return 0

    if not shutil.which("ffmpeg"):
        print("ffmpeg not found on PATH.", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = args.out or Path("outputs") / f"{args.plan.stem}.mp4"

    from services.plan_mode.runner import run_plan  # heavy imports only for a real run

    result = asyncio.run(run_plan(plan, out, plan_dir=args.plan.resolve().parent))
    print(f"\nDone: {result.video_path.resolve()} ({result.duration_seconds:.0f}s)")
    print(f"Credits/metadata: {result.credits_path}")
    for w in result.warnings:
        print(f"warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
