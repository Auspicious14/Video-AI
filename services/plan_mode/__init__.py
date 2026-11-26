"""Plan-file mode: render a documentary from a hand-written production.json.

No LLM calls happen anywhere under this package. See PLAN_MODE.md.
Importing this package is intentionally cheap; the heavy pieces (asset
providers, TTS, ffmpeg) live in ``services.plan_mode.runner`` and are only
imported by a real (non --dry-run) run.
"""
