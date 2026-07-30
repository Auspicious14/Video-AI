from __future__ import annotations

from pydantic import BaseModel, Field

from services.ai.media.asset_types import AssetKind


class MediaAsset(BaseModel):
    """
    A candidate visual returned from any provider.
    """

    url: str

    kind: AssetKind

    provider: str

    provider_id: str

    title: str = ""

    description: str = ""

    tags: list[str] = Field(default_factory=list)

    preview_url: str | None = None

    author: str | None = None

    relevance: float = 0.80

    quality: float = 0.80

    width: int = 1080

    height: int = 1920

    aspect_ratio: float = 9 / 16

    freshness: float = 0.80

    credibility: float = 0.80

    licensing: str = "unknown"

    score: float = 0.0