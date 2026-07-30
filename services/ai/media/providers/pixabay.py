from __future__ import annotations

import logging
import os
import urllib.parse

import requests

from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)


class PixabayProvider(MediaProvider):

    @property
    def name(self) -> str:
        return "pixabay"

    @property
    def supported_kinds(self) -> set[AssetKind]:
        return {AssetKind.STOCK_VIDEO, AssetKind.STOCK_IMAGE}

    @property
    def priority(self) -> int:
        return 35  # just behind Pexels (30) — matches the tier ordering in asset_collection.py

    def is_configured(self) -> bool:
        return bool(os.getenv("PIXABAY_API_KEY"))

    async def search(
        self,
        intent: VisualIntent,
        limit: int = 5,
    ) -> list[MediaAsset]:

        token = os.getenv("PIXABAY_API_KEY")
        if not token:
            return []

        # Pixabay caps q at 100 chars and requires per_page in [3, 200]
        query = intent.concise_search_query[:100]
        per_page = max(3, min(limit, 200))

        logger.info("[Pixabay] Searching: %s", query)

        wants_video = intent.preferred_asset_kind == AssetKind.STOCK_VIDEO

        if wants_video:
            url = (
                "https://pixabay.com/api/videos/"
                f"?key={token}&q={urllib.parse.quote(query)}"
                f"&per_page={per_page}&video_type=film&safesearch=true"
            )
        else:
            url = (
                "https://pixabay.com/api/"
                f"?key={token}&q={urllib.parse.quote(query)}"
                f"&per_page={per_page}&image_type=photo&safesearch=true"
            )

        assets: list[MediaAsset] = []

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            items = data.get("hits", [])

            for item in items:
                if wants_video:
                    videos = item.get("videos", {})
                    # Prefer the largest rendition available, falling back down
                    file_info = (
                        videos.get("large")
                        or videos.get("medium")
                        or videos.get("small")
                        or videos.get("tiny")
                    )
                    if not file_info or not file_info.get("url"):
                        continue

                    file_url = file_info["url"]
                    width = file_info.get("width", 1920)
                    height = file_info.get("height", 1080)
                    aspect = width / height if height else 16 / 9

                    asset_kind = AssetKind.STOCK_VIDEO
                    title = item.get("tags", "")
                    description = item.get("tags", "")
                    preview = None
                    author = item.get("user", "")

                else:
                    file_url = item.get("largeImageURL")
                    if not file_url:
                        continue

                    width = item.get("imageWidth", 1920)
                    height = item.get("imageHeight", 1080)
                    aspect = width / height if height else 16 / 9

                    asset_kind = AssetKind.STOCK_IMAGE
                    title = item.get("tags", "")
                    description = item.get("tags", "")
                    preview = item.get("previewURL") or item.get("webformatURL")
                    author = item.get("user", "")

                assets.append(
                    MediaAsset(
                        url=file_url,
                        kind=asset_kind,
                        provider=self.name,
                        provider_id=str(item.get("id", "")),
                        title=title,
                        description=description,
                        preview_url=preview,
                        author=author,
                        relevance=0.85,
                        quality=0.85,
                        width=width,
                        height=height,
                        aspect_ratio=aspect,
                        freshness=0.80,
                        credibility=0.80,
                        licensing="pixabay_free",
                    )
                )

        except Exception as exc:
            logger.exception("Pixabay search failed: %s", exc)

        logger.info(f"[Pixabay] Returned {len(assets)} assets for query: {query}")
        return assets