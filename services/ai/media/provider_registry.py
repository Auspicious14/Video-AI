from __future__ import annotations

from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider


class ProviderRegistry:

    def __init__(self):

        self.providers: list[MediaProvider] = []

    def register(
        self,
        provider: MediaProvider,
    ):

        self.providers.append(provider)

    def configured(self):

        return [

            p

            for p in self.providers

            if p.is_configured()

        ]

    def providers_for(
        self,
        kind: AssetKind,
    ):

        return [

            p

            for p in self.configured()

            if kind in p.supported_kinds

        ]