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


class PexelsProvider(MediaProvider):

    @property
    def name(self) -> str:
        return "pexels"

    @property
    def supported_kinds(self) -> set[AssetKind]:
        return {AssetKind.STOCK_VIDEO, AssetKind.STOCK_IMAGE}

    @property
    def priority(self) -> int:
        return 30

    def is_configured(self) -> bool:
        return bool(os.getenv("PEXELS_API_KEY"))

    async def search(
        self,
        intent: VisualIntent,
        limit: int = 5,
    ) -> list[MediaAsset]:

        token = os.getenv("PEXELS_API_KEY")

        if not token:
            return []

        # Use concise keyword search for better relevance
        query = intent.concise_search_query

        logger.info(
            "[Pexels] Searching: %s",
            query,
        )

        headers = {
            "Authorization": token,
        }

        wants_video = (
            intent.preferred_asset_kind
            == AssetKind.STOCK_VIDEO
        )

        if wants_video:

            url = (
                "https://api.pexels.com/videos/search"
                f"?query={urllib.parse.quote(query)}"
                f"&per_page={limit}"
            )

        else:

            url = (
                "https://api.pexels.com/v1/search"
                f"?query={urllib.parse.quote(query)}"
                f"&per_page={limit}"
            )

        assets: list[MediaAsset] = []

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=15,
            )

            response.raise_for_status()

            data = response.json()

            items = (
                data.get("videos", [])
                if wants_video
                else data.get("photos", [])
            )

            for item in items:

                width = item.get("width", 1080)
                height = item.get("height", 1920)

                aspect = (
                    width / height
                    if height
                    else 9 / 16
                )

                if wants_video:

                    file_url = None

                    for video in item.get("video_files", []):

                        if (
                            video.get("file_type")
                            == "video/mp4"
                        ):

                            file_url = video.get("link")

                            width = video.get(
                                "width",
                                width,
                            )

                            height = video.get(
                                "height",
                                height,
                            )

                            aspect = (
                                width / height
                                if height
                                else 9 / 16
                            )

                            break

                    if not file_url:
                        continue

                    preview = None

                    pictures = item.get(
                        "video_pictures",
                        [],
                    )

                    if pictures:
                        preview = pictures[0].get("picture")

                    asset_kind = AssetKind.STOCK_VIDEO

                    title = item.get("url", "")

                    description = ""

                    author = (
                        item.get("user", {})
                        .get("name", "")
                    )

                else:

                    src = item.get("src", {})

                    file_url = src.get("large2x")

                    if not file_url:
                        continue

                    preview = src.get("medium")

                    asset_kind = AssetKind.STOCK_IMAGE

                    title = item.get("alt", "")

                    description = item.get("alt", "")

                    author = item.get(
                        "photographer",
                        "",
                    )

                assets.append(

                    MediaAsset(

                        url=file_url,

                        kind=asset_kind,

                        provider=self.name,

                        provider_id=str(item["id"]),

                        title=title,

                        description=description,

                        preview_url=preview,

                        author=author,

                        relevance=0.90,

                        quality=0.90,

                        width=width,

                        height=height,

                        aspect_ratio=aspect,

                        freshness=0.90,

                        credibility=0.85,

                        licensing="pexels_free",

                    )

                )

        except Exception as exc:

            logger.exception(
                "Pexels search failed: %s",
                exc,
            )

        logger.info(f"[Pexels] Returned {len(assets)} assets for query: {query}")
        return assets
