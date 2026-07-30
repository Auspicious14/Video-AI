from __future__ import annotations

import asyncio
import logging

from services.ai.media.asset import MediaAsset
from services.ai.media.default_registry import build_registry
from services.ai.media.ranking import rank_assets
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)


class RetrievalOrchestrator:

    def __init__(self):

        self.registry = build_registry()

    async def retrieve(
        self,
        intent: VisualIntent,
        limit: int = 10,
    ) -> list[MediaAsset]:

        providers = self.registry.providers_for(
            intent.preferred_asset_kind
        )

        if not providers:

            logger.warning(
                "No providers available for %s",
                intent.preferred_asset_kind,
            )

            return []

        logger.info(
            "Searching %d providers for %s",
            len(providers),
            intent.subject,
        )

        tasks = [

            provider.search(
                intent,
                limit=limit,
            )

            for provider in providers

        ]

        results = await asyncio.gather(

            *tasks,

            return_exceptions=True,

        )

        assets: list[MediaAsset] = []

        for provider, result in zip(providers, results):

            if isinstance(result, Exception):

                logger.warning(
                    "%s failed: %s",
                    provider.name,
                    result,
                )

                continue

            assets.extend(result)

        logger.info(
            "Collected %d assets",
            len(assets),
        )

        assets = self._deduplicate(
            assets,
        )

        ranked = rank_assets(
            assets,
            intent,
        )

        return ranked[:limit]

    def _deduplicate(
        self,
        assets: list[MediaAsset],
    ) -> list[MediaAsset]:

        unique = {}

        for asset in assets:

            key = asset.url.strip().lower()

            if key not in unique:

                unique[key] = asset

                continue

            existing = unique[key]

            existing_score = (
                existing.relevance
                + existing.quality
                + existing.credibility
            )

            new_score = (
                asset.relevance
                + asset.quality
                + asset.credibility
            )

            if new_score > existing_score:

                unique[key] = asset

        logger.info(
            "Deduplicated %d → %d assets",
            len(assets),
            len(unique),
        )

        return list(unique.values())