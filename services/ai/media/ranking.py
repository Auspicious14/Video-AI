"""
services/ai/media/ranking.py — Media Ranking Engine

Responsibility:
Sort candidate assets collected for a scene MediaPlan by scoring their:
  - Relevance to query
  - Sourcing/technical quality
  - Resolution (higher is better)
  - Aspect ratio similarity (e.g., target 9:16 vs square vs landscape)
  - Freshness (age)
  - Source credibility
  - License permissiveness (CC0 / Public Domain / free vs restrictive)
"""

from __future__ import annotations

import logging
from typing import Any, List
from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)


def _asset_kind(asset: Any) -> str:
    kind = getattr(asset, "kind", None)
    if isinstance(kind, AssetKind):
        return kind.value
    if kind:
        return str(kind)
    return str(getattr(asset, "media_type", "stock_image"))


def _target_kind(intent_or_plan: Any) -> str:
    preferred = getattr(intent_or_plan, "preferred_asset_kind", None)
    if isinstance(preferred, AssetKind):
        return preferred.value
    if preferred:
        return str(preferred)
    return str(getattr(intent_or_plan, "media_type", "stock_image"))


def score_asset(asset: MediaAsset, intent: VisualIntent, target_aspect: float = 0.5625) -> float:
    """
    Computes a weighted quality score between 0.0 and 1.0 for a single MediaAsset.
    
    Weights:
      - Relevance: 0.25
      - Technical Quality: 0.15
      - Resolution: 0.15
      - Aspect Ratio Match: 0.20
      - Freshness: 0.10
      - Source Credibility: 0.05
      - License Permissiveness: 0.10
    """
    # ── 1. Relevance ──────────────────────────────────────────────────────────
    # Planner media type match booster
    type_match_boost = 1.0 if _asset_kind(asset).lower() == _target_kind(intent).lower() else 0.5
    relevance_score = asset.relevance * type_match_boost

    # ── 2. Technical Quality ──────────────────────────────────────────────────
    quality_score = asset.quality

    # ── 3. Resolution Score ───────────────────────────────────────────────────
    # We prefer at least 1080 width or height depending on orientation
    total_pixels = asset.width * asset.height
    if total_pixels >= 1920 * 1080:
        res_score = 1.0
    elif total_pixels >= 1280 * 720:
        res_score = 0.8
    elif total_pixels >= 854 * 480:
        res_score = 0.6
    else:
        res_score = 0.4

    # ── 4. Aspect Ratio Score ─────────────────────────────────────────────────
    # Measure absolute deviation from target aspect ratio
    aspect_diff = abs(asset.aspect_ratio - target_aspect)
    if aspect_diff < 0.05:
        aspect_score = 1.0  # Perfect fit (e.g. vertical 9:16)
    elif aspect_diff < 0.15:
        aspect_score = 0.9  # Close enough vertical
    elif abs(asset.aspect_ratio - 1.0) < 0.05:
        aspect_score = 0.7  # Square 1:1 (easy to crop with zoompan)
    elif abs(asset.aspect_ratio - (16/9)) < 0.1:
        aspect_score = 0.5  # Landscape (needs high crop)
    else:
        aspect_score = 0.3

    # ── 5. Freshness Score ────────────────────────────────────────────────────
    freshness_score = asset.freshness

    # ── 6. Source Credibility ─────────────────────────────────────────────────
    credibility_score = asset.credibility

    # ── 7. License Score ──────────────────────────────────────────────────────
    license_clean = asset.licensing.strip().lower()
    if license_clean in ("cc0", "public_domain", "publicdomain", "cc0_simulation"):
        license_score = 1.0
    elif license_clean in ("pexels_free", "unsplash_free", "creative_commons", "free"):
        license_score = 0.9
    elif license_clean in ("editorial", "commercial_allowed"):
        license_score = 0.7
    else:
        license_score = 0.4  # Restricted / Unknown

    # ── Weighted Sum ──────────────────────────────────────────────────────────
    total_score = (
        0.25 * relevance_score +
        0.15 * quality_score +
        0.15 * res_score +
        0.20 * aspect_score +
        0.10 * freshness_score +
        0.05 * credibility_score +
        0.10 * license_score
    )

    logger.debug(
        "[Ranking] Scored asset from %s | Type: %s | Final: %.3f "
        "(Rel: %.2f, Qual: %.2f, Res: %.2f, Aspect: %.2f, Lic: %.2f)",
        asset.provider, _asset_kind(asset), total_score,
        relevance_score, quality_score, res_score, aspect_score, license_score
    )

    return total_score


def rank_assets(
    assets: List[MediaAsset],
    intent: VisualIntent,
    target_aspect: float = 0.5625,
    min_score_threshold: float = 0.45,
) -> List[MediaAsset]:
    """
    Scores and ranks a list of candidate assets.
    Filters out assets that fall below the minimum quality/score threshold.
    
    Returns
    -------
    List[MediaAsset] sorted in descending order of score.
    """
    if not assets:
        return []

    scored_pairs = []
    for asset in assets:
        score = score_asset(asset, intent, target_aspect=target_aspect)
        try:
            asset.score = round(score * 10.0, 4)
        except Exception:
            pass
        if score >= min_score_threshold:
            scored_pairs.append((score, asset))
        else:
            logger.debug("[Ranking] Filtered out asset from %s due to low score: %.3f", asset.provider, score)

    # Sort descending by score
    scored_pairs.sort(key=lambda x: x[0], reverse=True)
    
    ranked_assets = [asset for score, asset in scored_pairs]
    logger.info(
        "[Ranking] Ranked %d candidates. Best score: %.3f (%s from %s)",
        len(ranked_assets),
        scored_pairs[0][0] if scored_pairs else 0.0,
        _asset_kind(ranked_assets[0]) if ranked_assets else "None",
        ranked_assets[0].provider if ranked_assets else "None"
    )

    return ranked_assets
