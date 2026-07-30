from __future__ import annotations

from services.ai.media.asset import MediaAsset
from services.ai.media.scoring.scorer import AssetScorer
from services.ai.media.visual_intent import VisualIntent


class RankingEngine:

    def __init__(self):

        self.scorer = AssetScorer()

    def rank(
        self,
        assets: list[MediaAsset],
        intent: VisualIntent,
    ) -> list[MediaAsset]:

        scored = []

        for asset in assets:

            score = self.scorer.score(asset, intent)

            asset.score = score

            scored.append(asset)

        scored.sort(
            key=lambda x: x.score,
            reverse=True,
        )

        return scored