from __future__ import annotations

from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider


class RetrievalPolicy:

    MAX_PROVIDERS = 3

    def select(
        self,
        providers: list[MediaProvider],
        kind: AssetKind,
    ) -> list[MediaProvider]:

        matching = [

            p

            for p in providers

            if kind in p.supported_kinds

        ]

        matching.sort(

            key=lambda p: p.priority,

        )

        return matching[: self.MAX_PROVIDERS]