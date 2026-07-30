from __future__ import annotations

from services.ai.media.asset import MediaAsset
from services.ai.media.visual_intent import VisualIntent


class AssetScorer:

    TARGET_ASPECT = 9 / 16

    def score(
        self,
        asset: MediaAsset,
        intent: VisualIntent,
    ) -> float:

        score = 0.0

        score += self._provider_score(asset) * 0.10
        score += self._kind_score(asset, intent) * 0.20
        score += self._quality_score(asset) * 0.20
        score += self._resolution_score(asset) * 0.15
        score += self._aspect_score(asset) * 0.10
        score += self._license_score(asset) * 0.10
        score += self._relevance_score(asset) * 0.15

        return round(score, 4)

    def _provider_score(self, asset: MediaAsset):

        weights = {
            "wikimedia": 1.0,
            "pexels": 0.95,
            "unsplash": 0.9,
            "simulation": 0.2,
        }

        return weights.get(asset.provider, 0.5)

    def _kind_score(
        self,
        asset,
        intent,
    ):

        return 1.0 if asset.kind == intent.preferred_asset_kind else 0.4

    def _quality_score(self, asset):

        return asset.quality

    def _resolution_score(self, asset):

        pixels = asset.width * asset.height

        if pixels >= 1920 * 1080:
            return 1

        if pixels >= 1280 * 720:
            return 0.8

        if pixels >= 854 * 480:
            return 0.6

        return 0.3

    def _aspect_score(self, asset):

        diff = abs(asset.aspect_ratio - self.TARGET_ASPECT)

        if diff < 0.05:
            return 1

        if diff < 0.15:
            return 0.8

        return 0.5

    def _license_score(self, asset):

        mapping = {
            "public_domain": 1,
            "creative_commons": 0.95,
            "pexels_free": 0.95,
            "unsplash_free": 0.9,
            "unknown": 0.4,
        }

        return mapping.get(asset.licensing, 0.5)

    def _relevance_score(self, asset):

        return asset.relevance
