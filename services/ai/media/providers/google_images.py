from __future__ import annotations

import logging
import os
import requests

from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)


class GoogleImagesProvider(MediaProvider):

    @property
    def name(self) -> str:
        return "google_images"

    @property
    def supported_kinds(self) -> set[AssetKind]:
        return {
            AssetKind.STOCK_IMAGE,
            AssetKind.HISTORICAL_PHOTO,
            AssetKind.LOGO,
            AssetKind.PRODUCT,
            AssetKind.SCREENSHOT,
            AssetKind.WEBSITE,
        }

    @property
    def priority(self) -> int:
        return 60

    def is_configured(self) -> bool:
        return bool(
            os.getenv("GOOGLE_SEARCH_API_KEY")
            and os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        )

    async def search(
        self,
        intent: VisualIntent,
        limit: int = 5,
    ) -> list[MediaAsset]:

        api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        engine = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

        if not api_key or not engine:
            return []

        query = " ".join([
            intent.subject,
            intent.action,
            *intent.search_keywords,
        ])

        params = {
            "key": api_key,
            "cx": engine,
            "q": query,
            "searchType": "image",
            "num": min(limit, 10),
            "safe": "active",
        }

        try:

            response = requests.get(
                "https://customsearch.googleapis.com/customsearch/v1",
                params=params,
                timeout=20,
            )

            response.raise_for_status()

            data = response.json()

            assets = []

            for item in data.get("items", []):

                image = item.get("image", {})

                width = image.get("width", 1920)
                height = image.get("height", 1080)

                assets.append(

                    MediaAsset(
                        provider_id=item.get("cacheId", item["link"]),
                        title=item.get("title", ""),
                        description=item.get("snippet", ""),
                        author=item.get("displayLink", ""),
                        preview_url=item["link"],
                        url=item["link"],
                        provider=self.name,
                        kind=AssetKind.STOCK_IMAGE,
                        relevance=.85,
                        quality=.75,
                        width=width,
                        height=height,
                        aspect_ratio=width / max(height, 1),
                        freshness=.80,
                        credibility=.70,
                        licensing="unknown",
                    )
                )

            return assets

        except Exception as exc:

            logger.warning(
                "Google Images search failed: %s",
                exc,
            )

            return []
