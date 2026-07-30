"""
services/ai/media — Intelligent Media Acquisition Engine exports
"""

from __future__ import annotations


async def acquire_media_assets(*args, **kwargs):
    from services.ai.media.coordinator import acquire_media_assets as _acquire
    return await _acquire(*args, **kwargs)
