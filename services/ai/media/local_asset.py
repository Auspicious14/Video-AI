from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel

from services.ai.media.asset_types import AssetKind


class LocalAsset(BaseModel):
    """
    A validated media asset stored locally.

    This is the object that the renderer will consume.
    """

    source_provider: str

    provider_id: str

    local_path: Path

    kind: AssetKind

    width: int

    height: int

    duration: float | None = None

    fps: float | None = None

    filesize: int

    mime_type: str

    checksum: str

    score: float

    metadata: dict = {}