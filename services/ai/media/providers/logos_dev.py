from __future__ import annotations

import logging
import requests
import os
from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)


class LogosDevProvider(MediaProvider):

    @property
    def name(self) -> str:
        return "logos_dev"

    @property
    def supported_kinds(self) -> set[AssetKind]:
        return {AssetKind.LOGO}

    @property
    def priority(self) -> int:
        return 10

    def is_configured(self) -> bool:
        return bool(os.getenv("LOGO_DEV_API_KEY"))

    async def search(
        self,
        intent: VisualIntent,
        limit: int = 1,
    ) -> list[MediaAsset]:
        api_key = os.getenv("LOGO_DEV_API_KEY")

        if not api_key or intent.preferred_asset_kind != AssetKind.LOGO:
            return []
        entity = next(
            (
                part
                for part in [*intent.search_keywords, intent.location or "", intent.subject]
                if isinstance(part, str) and "." in part and " " not in part.strip()
            ),
            "",
        )

        if not entity:
            return []

        domain = (
            entity
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )
        logo_url = f"https://img.logo.dev/{domain}?token={api_key}"

        try:
            response = requests.get(logo_url, timeout=20)
            if response.status_code != 200:
                return []

            return [
                MediaAsset(
                    provider_id=domain,
                    title=domain,
                    description="Company Logo",
                    author="logos.dev",
                    preview_url=logo_url,
                    url=logo_url,
                    provider=self.name,
                    kind=AssetKind.LOGO,
                    relevance=1.0,
                    quality=.98,
                    width=1024,
                    height=1024,
                    aspect_ratio=1,
                    freshness=1.0,
                    credibility=.99,
                    licensing="commercial",
                )
            ]

        except Exception as exc:

            logger.warning(
                "Logo lookup failed: %s",
                exc,
            )
            return []
