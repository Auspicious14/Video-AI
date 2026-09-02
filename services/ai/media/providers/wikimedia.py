from __future__ import annotations

import logging
import urllib.parse

import requests

from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "SecondOrderDocumentaryBot/1.0 (+https://auspicious.vercel.app; mailto:uthmanabdulganiyu2019@gmail.com)"
}

class WikimediaProvider(MediaProvider):

    @property
    def name(self) -> str:
        return "wikimedia"

    @property
    def supported_kinds(self) -> set[AssetKind]:
        return {
            AssetKind.STOCK_IMAGE,
            AssetKind.HISTORICAL_PHOTO,
            AssetKind.LOGO,
            AssetKind.MAP,
            AssetKind.CHART,
            AssetKind.INFOGRAPHIC,
        }

    @property
    def priority(self) -> int:
        return 20

    def is_configured(self) -> bool:
        return True

    async def search(
        self,
        intent: VisualIntent,
        limit: int = 5,
    ) -> list[MediaAsset]:

        query = intent.concise_search_query  # Use concise keyword extraction
        
        # Wikimedia Commons requires concise queries, not paragraphs
        logger.info(f"[Wikimedia] Searching with keywords: {query}")

        assets: list[MediaAsset] = []

        try:

            encoded = urllib.parse.quote(query)

            search_url = (
                "https://commons.wikimedia.org/w/api.php?"
                "action=query"
                "&list=search"
                "&srnamespace=6"
                "&format=json"
                "&origin=*"
                f"&srsearch={encoded}"
            )

            response = requests.get(search_url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            data = response.json()

            results = (
                data.get("query", {})
                .get("search", [])
            )

            for item in results[:limit]:
                title = item.get("title")
                if not title:
                    continue
                info_url = (
                    "https://commons.wikimedia.org/w/api.php?"
                    "action=query"
                    "&prop=imageinfo"
                    "&iiprop=url|size|mime"
                    "&format=json"
                    "&origin=*"
                    f"&titles={urllib.parse.quote(title)}"
                )
                info = requests.get(info_url, headers=HEADERS, timeout=20)
                info.raise_for_status()

                pages = (
                    info.json()
                    .get("query", {})
                    .get("pages", {})
                )

                for page in pages.values():
                    imageinfo = page.get("imageinfo")
                    if not imageinfo:
                        continue
                    img = imageinfo[0]
                    url = img.get("url")
                    if not url:
                        continue
                    mime = img.get("mime", "")
                    ALLOWED_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
                    if mime.lower() not in ALLOWED_MIMES:
                        continue
                    width = img.get("width", 1920)
                    height = img.get("height", 1080)

                    assets.append(
                        MediaAsset(
                            provider_id=title,
                            title=title,
                            description=item.get("snippet", ""),
                            author="Wikimedia Commons",
                            preview_url=url,
                            url=url,
                            provider=self.name,
                            kind=intent.preferred_asset_kind,  # Fixed: was intent.kind
                            relevance=.90,
                            quality=.85,
                            width=width,
                            height=height,
                            aspect_ratio=width / max(height, 1),
                            freshness=.60,
                            credibility=.98,
                            licensing="public_domain",
                        )
                    )

        except Exception as exc:
            logger.warning(
                "Wikimedia search failed: %s",
                exc,
            )

        logger.info(f"[Wikimedia] Returned {len(assets)} assets")
        return assets
