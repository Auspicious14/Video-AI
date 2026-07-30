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


class UnsplashProvider(MediaProvider):

    @property
    def name(self) -> str:
        return "unsplash"

    @property
    def supported_kinds(self) -> set[AssetKind]:
        return {AssetKind.STOCK_IMAGE, AssetKind.HISTORICAL_PHOTO}

    @property
    def priority(self) -> int:
        return 70

    def is_configured(self) -> bool:
        return bool(
            os.getenv("UNSPLASH_ACCESS_KEY")
            or os.getenv("UNSPLASH_API_KEY")
        )

    async def search(
        self,
        intent: VisualIntent,
        limit: int = 5,
    ) -> list[MediaAsset]:

        token = (
            os.getenv("UNSPLASH_ACCESS_KEY")
            or os.getenv("UNSPLASH_API_KEY")
        )

        if not token:
            return []

        # Prefer concise keywords for better search results
        # Unsplash works better with focused queries than long descriptions
        query = intent.concise_search_query.strip()

        logger.info(
            "[Unsplash] Searching for: %s",
            query,
        )

        headers = {
            "Authorization": f"Client-ID {token}"
        }

        url = (
            "https://api.unsplash.com/search/photos"
            f"?query={urllib.parse.quote(query)}"
            f"&per_page={limit}"
        )

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=20,
            )

            response.raise_for_status()

            data = response.json()

            assets: list[MediaAsset] = []

            for item in data.get("results", []):

                image_url = item.get("urls", {}).get("regular")

                if not image_url:
                    continue

                width = item.get("width", 1080)
                height = item.get("height", 1920)

                assets.append(

                    MediaAsset(

                        provider_id=str(item["id"]),

                        title=item.get("description")
                        or item.get("alt_description")
                        or "",

                        description=item.get("alt_description")
                        or "",

                        author=item.get("user", {}).get("name", ""),

                        preview_url=item.get("urls", {}).get("small", image_url),

                        url=image_url,

                        provider=self.name,

                        kind=intent.preferred_asset_kind,  # Fixed: was intent.kind

                        relevance=0.90,

                        quality=0.92,

                        width=width,

                        height=height,

                        aspect_ratio=width / max(height, 1),

                        freshness=0.90,

                        credibility=0.88,

                        licensing="unsplash_free",
                    )

                )

            logger.info(f"[Unsplash] Returned {len(assets)} assets")
            return assets

        except Exception as exc:

            logger.warning(
                "[Unsplash] Search failed: %s",
                exc,
            )

            return []
