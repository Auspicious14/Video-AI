from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

from config import OUTPUT_DIR

from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = OUTPUT_DIR / "website_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class WebsiteProvider(MediaProvider):

    @property
    def name(self) -> str:
        return "website"

    @property
    def supported_kinds(self) -> set[AssetKind]:
        return {AssetKind.WEBSITE, AssetKind.SCREENSHOT}

    @property
    def priority(self) -> int:
        return 10

    def is_configured(self) -> bool:
        return True

    async def search(
        self,
        intent: VisualIntent,
        limit: int = 1,
    ) -> list[MediaAsset]:

        if intent.preferred_asset_kind not in {AssetKind.WEBSITE, AssetKind.SCREENSHOT}:
            return []

        domain = next(
            (
                part
                for part in [*intent.search_keywords, intent.location or "", intent.subject]
                if isinstance(part, str) and (part.startswith("http://") or part.startswith("https://"))
            ),
            "",
        )

        if not domain:
            return []

        screenshot_url = (
            "https://image.thum.io/get/width/1600/"
            + domain
        )

        filename = hashlib.md5(domain.encode()).hexdigest() + ".jpg"

        local_path = SCREENSHOT_DIR / filename

        try:

            if not local_path.exists():

                response = requests.get(
                    screenshot_url,
                    timeout=30,
                )

                response.raise_for_status()

                local_path.write_bytes(response.content)

            return [

                MediaAsset(

                    provider_id=domain,

                    title=domain,

                    description="Website Screenshot",

                    author=domain,

                    preview_url=str(local_path),

                    url=str(local_path),

                    provider=self.name,

                    kind=AssetKind.WEBSITE,

                    relevance=1.0,

                    quality=.95,

                    width=1600,

                    height=900,

                    aspect_ratio=1600 / 900,

                    freshness=1.0,

                    credibility=.95,

                    licensing="editorial",

                )

            ]

        except Exception as exc:

            logger.warning(
                "Website screenshot failed: %s",
                exc,
            )

            return []
