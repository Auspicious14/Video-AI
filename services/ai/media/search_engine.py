"""
Unified Media Search Engine

Responsibilities

1. Accept a VisualIntent

2. Query every provider concurrently

3. Merge all candidates

4. Remove duplicates

5. Return one unified asset pool

Nothing else in the system should know which providers exist.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict

from services.ai.media.visual_intent import VisualIntent
from services.ai.media.collector import MediaAsset
from services.ai.media.providers.base import MediaProvider

logger = logging.getLogger(__name__)


class MediaSearchEngine:

    def __init__(self):

        self.providers: list[MediaProvider] = []

    def register(self, provider: MediaProvider):

        self.providers.append(provider)

        logger.info("Registered provider: %s", provider.name)

    async def search(
        self,
        intent: VisualIntent,
        limit_per_provider: int = 8,
    ) -> list[MediaAsset]:

        if not self.providers:
            return []

        tasks = [
            provider.search(
                intent,
                limit_per_provider,
            )
            for provider in self.providers
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        assets: list[MediaAsset] = []

        for provider, result in zip(self.providers, results):

            if isinstance(result, Exception):

                logger.exception(
                    "Provider %s failed",
                    provider.name,
                    exc_info=result,
                )

                continue

            assets.extend(result)

        return self._deduplicate(assets)

    def _deduplicate(
        self,
        assets: list[MediaAsset],
    ) -> list[MediaAsset]:

        unique = OrderedDict()

        for asset in assets:

            key = asset.url

            if key not in unique:
                unique[key] = asset

        return list(unique.values())