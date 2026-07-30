"""Stage 7: real asset collection before AI generation."""

from __future__ import annotations

import logging

from services.ai.media.asset_types import AssetKind
from services.ai.media.visual_intent import CameraMotion, Emotion, ShotType, SubjectType, VisualIntent
from services.ai.schemas import (
    AssetCandidate,
    AssetCollectionResult,
    QualityIssue,
    VisualAssetSpec,
    VisualPlanResult,
    VisualTimelineItem,
    VisualType,
)

logger = logging.getLogger(__name__)


_VIDEO_TYPES = {
    VisualType.STOCK_VIDEO,
    VisualType.STOCK_FOOTAGE,
    VisualType.HISTORICAL_FOOTAGE,
    VisualType.DOCUMENTARY_FOOTAGE,
    VisualType.NEWS_FOOTAGE,
    VisualType.OFFICIAL_COMPANY_VIDEO,
    VisualType.PRODUCT_FOOTAGE,
    VisualType.DRONE_FOOTAGE,
    VisualType.B_ROLL,
    VisualType.UI_RECORDING,
    VisualType.SCREEN_RECORDING,
}

_GRAPHIC_TYPES = {
    VisualType.CHART,
    VisualType.MAP,
    VisualType.TIMELINE,
    VisualType.TIMELINE_ANIMATION,
    VisualType.MOTION_GRAPHIC,
    VisualType.INFOGRAPHIC,
}

_VISUAL_TO_ASSET_KIND = {
    VisualType.STOCK_VIDEO: AssetKind.STOCK_VIDEO,
    VisualType.STOCK_FOOTAGE: AssetKind.STOCK_VIDEO,
    VisualType.HISTORICAL_FOOTAGE: AssetKind.STOCK_VIDEO,
    VisualType.DOCUMENTARY_FOOTAGE: AssetKind.STOCK_VIDEO,
    VisualType.NEWS_FOOTAGE: AssetKind.STOCK_VIDEO,
    VisualType.OFFICIAL_COMPANY_VIDEO: AssetKind.STOCK_VIDEO,
    VisualType.PRODUCT_FOOTAGE: AssetKind.STOCK_VIDEO,
    VisualType.DRONE_FOOTAGE: AssetKind.STOCK_VIDEO,
    VisualType.B_ROLL: AssetKind.STOCK_VIDEO,
    VisualType.STOCK_IMAGE: AssetKind.STOCK_IMAGE,
    VisualType.HISTORICAL_PHOTO: AssetKind.HISTORICAL_PHOTO,
    VisualType.COMPANY_PRESS_IMAGE: AssetKind.STOCK_IMAGE,
    VisualType.OFFICIAL_PRODUCT_IMAGE: AssetKind.PRODUCT,
    VisualType.SCREENSHOT: AssetKind.SCREENSHOT,
    VisualType.WEBSITE_CAPTURE: AssetKind.WEBSITE,
    VisualType.UI_RECORDING: AssetKind.STOCK_VIDEO,
    VisualType.SCREEN_RECORDING: AssetKind.STOCK_VIDEO,
    VisualType.CHART: AssetKind.CHART,
    VisualType.MAP: AssetKind.MAP,
    VisualType.TIMELINE: AssetKind.INFOGRAPHIC,
    VisualType.TIMELINE_ANIMATION: AssetKind.INFOGRAPHIC,
    VisualType.MOTION_GRAPHIC: AssetKind.INFOGRAPHIC,
    VisualType.INFOGRAPHIC: AssetKind.INFOGRAPHIC,
    VisualType.ANIMATION: AssetKind.AI_VIDEO,
    VisualType.PRODUCT_UI: AssetKind.PRODUCT,
    VisualType.LOGO: AssetKind.LOGO,
    VisualType.AI_IMAGE: AssetKind.AI_IMAGE,
    VisualType.AI_VIDEO: AssetKind.AI_VIDEO,
}

_PROVIDER_ORDER_BY_TIER = {
    "official": ["website", "google_images", "logos_dev"],
    "documentary_archive": ["wikimedia", "internet_archive", "library_of_congress"],
    "video": ["pexels", "pixabay", "coverr", "mixkit", "videvo"],
    "photo": ["wikimedia", "unsplash", "pexels", "pixabay", "google_images"],
    "local": ["local"],
}


def _visual_kind(visual_type: VisualType) -> AssetKind:
    return _VISUAL_TO_ASSET_KIND.get(visual_type, AssetKind.STOCK_IMAGE)


def _is_authentic_video_type(visual_type: VisualType) -> bool:
    return visual_type in _VIDEO_TYPES


def _provider_order_for_spec(spec: VisualAssetSpec) -> list[str]:
    preferred = [name.strip().lower() for name in spec.preferred_sources if name.strip()]
    order: list[str] = []
    for name in preferred:
        if name not in order:
            order.append(name)

    tiers = []
    if spec.visual_type in {
        VisualType.OFFICIAL_COMPANY_VIDEO,
        VisualType.COMPANY_PRESS_IMAGE,
        VisualType.OFFICIAL_PRODUCT_IMAGE,
        VisualType.LOGO,
        VisualType.WEBSITE_CAPTURE,
        VisualType.SCREENSHOT,
    }:
        tiers.append("official")
    if spec.visual_type in {VisualType.HISTORICAL_FOOTAGE, VisualType.DOCUMENTARY_FOOTAGE, VisualType.HISTORICAL_PHOTO}:
        tiers.append("documentary_archive")
    if _is_authentic_video_type(spec.visual_type):
        tiers.append("video")
    elif spec.visual_type not in {VisualType.AI_IMAGE, VisualType.AI_VIDEO}:
        tiers.append("photo")
    tiers.append("local")

    for tier in tiers:
        for provider in _PROVIDER_ORDER_BY_TIER[tier]:
            if provider not in order:
                order.append(provider)
    return order


def _ordered_providers(registry, kind: AssetKind, provider_order: list[str]):
    providers = registry.providers_for(kind)
    order_index = {name: idx for idx, name in enumerate(provider_order)}
    return sorted(
        providers,
        key=lambda p: (order_index.get(p.name, len(order_index)), p.priority),
    )


def _intent_for_asset(item: VisualTimelineItem, spec: VisualAssetSpec) -> VisualIntent:
    kind = _visual_kind(spec.visual_type)
    subject_type = SubjectType.SCREEN if spec.visual_type in {VisualType.SCREENSHOT, VisualType.WEBSITE_CAPTURE, VisualType.PRODUCT_UI} else SubjectType.OBJECT
    if spec.visual_type in _GRAPHIC_TYPES:
        subject_type = SubjectType.DOCUMENT
    if spec.visual_type in {VisualType.DRONE_FOOTAGE, VisualType.MAP}:
        shot_type = ShotType.AERIAL if spec.visual_type == VisualType.DRONE_FOOTAGE else ShotType.WIDE
    else:
        shot_type = ShotType.MEDIUM
    return VisualIntent(
        subject=spec.on_screen[:160] or item.on_screen[:160],
        subject_type=subject_type,
        action=item.narration_reference[:120] or "illustrate the narration",
        shot_type=shot_type,
        motion=CameraMotion.DRONE if spec.visual_type == VisualType.DRONE_FOOTAGE else CameraMotion.PUSH_IN,
        emotion=Emotion.SERIOUS,
        must_show=[spec.on_screen or item.on_screen],
        search_keywords=spec.search_queries or item.search_queries,
        preferred_sources=_provider_order_for_spec(spec),
        preferred_asset_kind=kind,
    )


async def run_asset_collection_service(
    *,
    visual_plan: VisualPlanResult,
    per_visual_limit: int = 3,
) -> AssetCollectionResult:
    """
    Attempt to collect real assets first.

    If no configured provider can satisfy a beat, the beat is marked for AI
    generation instead of failing the whole production.
    """
    registry = None
    used_asset_keys: set[tuple[str, str]] = set()
    selected: list[AssetCandidate] = []
    ai_required: list[int] = []
    issues: list[QualityIssue] = []

    for item in visual_plan.timeline:
        specs = item.assets or [
            VisualAssetSpec(
                asset_index=0,
                visual_type=item.asset_type,
                on_screen=item.on_screen,
                reason=item.reason,
                sourcing_priority=item.sourcing_priority,
                search_queries=item.search_queries,
                generation_prompt=item.generation_prompt,
                motion_direction=item.motion_direction,
            )
        ]

        beat_has_asset = False
        for spec in specs:
            if spec.sourcing_priority == "ai_only" or spec.visual_type in {VisualType.AI_IMAGE, VisualType.AI_VIDEO}:
                ai_required.append(item.index)
                continue

            kind = _visual_kind(spec.visual_type)
            if kind == AssetKind.AI_VIDEO:
                ai_required.append(item.index)
                continue

            if kind == AssetKind.STOCK_IMAGE and _is_authentic_video_type(item.asset_type):
                kind = AssetKind.STOCK_VIDEO

            if registry is None:
                try:
                    from services.ai.media.default_registry import build_registry

                    registry = build_registry()
                except Exception as exc:  # noqa: BLE001
                    ai_required.append(item.index)
                    issues.append(
                        QualityIssue(
                            severity="medium",
                            stage="asset_collection",
                            issue=f"Asset provider registry could not be loaded: {exc}",
                            recommendation="Install media provider dependencies or approve AI generation for this beat.",
                        )
                    )
                    continue

            providers = _ordered_providers(registry, kind, _provider_order_for_spec(spec))
            if not providers:
                ai_required.append(item.index)
                issues.append(
                    QualityIssue(
                        severity="low",
                        stage="asset_collection",
                        issue=f"No configured provider available for visual {item.index}.{spec.asset_index} ({kind.value}).",
                        recommendation="Configure an asset provider or approve AI generation for this beat.",
                    )
                )
                continue

            intent = _intent_for_asset(item, spec)
            
            # Log search intent
            logger.info(
                f"[AssetCollection] Visual {item.index}.{spec.asset_index}: "
                f"Searching for {kind.value} with query: {intent.concise_search_query}"
            )
            
            candidates = []
            for provider in providers:
                try:
                    provider_candidates = await provider.search(intent, limit=per_visual_limit)
                    if provider_candidates:
                        logger.info(
                            f"[AssetCollection] {provider.name} returned {len(provider_candidates)} candidates "
                            f"for visual {item.index}.{spec.asset_index}"
                        )
                    candidates.extend(provider_candidates)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Asset provider failed | provider=%s item=%s asset=%s error=%s", provider.name, item.index, spec.asset_index, exc)

            if not candidates and _is_authentic_video_type(spec.visual_type) and kind == AssetKind.STOCK_VIDEO:
                still_kind = AssetKind.HISTORICAL_PHOTO if spec.visual_type == VisualType.HISTORICAL_FOOTAGE else AssetKind.STOCK_IMAGE
                fallback_intent = intent.model_copy(update={"preferred_asset_kind": still_kind})
                for provider in _ordered_providers(registry, still_kind, _provider_order_for_spec(spec)):
                    try:
                        candidates.extend(await provider.search(fallback_intent, limit=per_visual_limit))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Still fallback provider failed | provider=%s item=%s asset=%s error=%s", provider.name, item.index, spec.asset_index, exc)

            if not candidates:
                logger.warning(
                    f"[AssetCollection] Visual {item.index}.{spec.asset_index}: "
                    f"No candidates found. Marking for AI generation."
                )
                ai_required.append(item.index)
                issues.append(
                    QualityIssue(
                        severity="medium",
                        stage="asset_collection",
                        issue=f"No usable real asset found for visual {item.index}.{spec.asset_index}.",
                        recommendation="Review search queries or use the AI fallback for this specific asset.",
                    )
                )
                continue

            # Sort candidates with strong preference for videos over images
            # Documentary channels prioritize video clips and motion
            def _asset_ranking_score(candidate):
                """
                Internal ranking score (0-100+ scale) used for sorting candidates.
                NOT the same as suitability_score (0-10 scale).
                """
                # Base score from provider ranking (already 0-10 scale)
                base_score = candidate.score or 0.0
                
                # MAJOR boost for video assets (documentary standard)
                # Videos are preferred 5x over images for documentary feel
                if candidate.kind in {AssetKind.STOCK_VIDEO, AssetKind.AI_VIDEO}:
                    video_bonus = 50.0
                else:
                    video_bonus = 0.0
                
                # Additional quality factors (fields are 0-1 scale from providers)
                # Scale them to 0-10 for ranking
                credibility_component = (candidate.credibility or 0.0) * 10.0
                quality_component = (candidate.quality or 0.0) * 10.0
                relevance_component = (candidate.relevance or 0.0) * 10.0
                
                # Total ranking score (can exceed 100)
                ranking_score = (
                    base_score + video_bonus + 
                    credibility_component + quality_component + relevance_component
                )
                return ranking_score
            
            def _calculate_suitability_score(candidate):
                """
                Calculate user-facing suitability score (0-10 scale) for AssetCandidate.
                This is separate from internal ranking score.
                
                Components (all normalized to 0-10):
                - Base quality: candidate.score (already 0-10)
                - Credibility: 0-1 → 0-10
                - Relevance: 0-1 → 0-10
                - Video bonus: +2 points for videos (not 50!)
                
                Average these for final 0-10 score.
                """
                base = candidate.score or 0.0  # 0-10
                credibility = (candidate.credibility or 0.0) * 10.0  # 0-1 → 0-10
                relevance = (candidate.relevance or 0.0) * 10.0  # 0-1 → 0-10
                
                # Video bonus for suitability (much smaller than ranking bonus)
                if candidate.kind in {AssetKind.STOCK_VIDEO, AssetKind.AI_VIDEO}:
                    video_adjustment = 2.0
                else:
                    video_adjustment = 0.0
                
                # Weighted average with video adjustment
                raw_score = (base * 0.4 + credibility * 0.2 + relevance * 0.4) + video_adjustment
                
                # Clamp to 0-10 range
                return min(10.0, max(0.0, raw_score))
            
            # Sort by internal ranking score (can be >100)
            ranked = sorted(candidates, key=_asset_ranking_score, reverse=True)
            best = next(
                (c for c in ranked if (c.provider, c.provider_id) not in used_asset_keys),
                ranked[0],  # every candidate already used — reuse the best rather than skip the beat
            )
            used_asset_keys.add((best.provider, best.provider_id))
            
            # Log selected candidate
            logger.info(
                f"[AssetCollection] Visual {item.index}.{spec.asset_index}: "
                f"Selected {best.kind.value} from {best.provider} "
                f"(ranking_score={_asset_ranking_score(best):.1f}, "
                f"quality={best.quality:.2f}, relevance={best.relevance:.2f})"
            )
            
            # Calculate suitability score (must be 0-10 for schema)
            suitability = _calculate_suitability_score(best)
            
            # Validate range before creating AssetCandidate
            assert 0.0 <= suitability <= 10.0, (
                f"suitability_score out of range: {suitability:.2f} "
                f"(base={best.score}, cred={best.credibility}, rel={best.relevance})"
            )
            
            selected.append(
                AssetCandidate(
                    visual_index=item.index,
                    asset_index=spec.asset_index,
                    source=best.provider,
                    asset_type=best.kind.value,
                    url=best.url,
                    license=best.licensing,
                    credit=best.author or best.title,
                    suitability_score=round(suitability, 2),
                    notes=best.description or best.title or spec.reason,
                )
            )
            beat_has_asset = True

        if not beat_has_asset and item.index not in ai_required:
            ai_required.append(item.index)

    # Summary logging
    video_count = sum(1 for a in selected if 'video' in a.asset_type.lower())
    image_count = len(selected) - video_count
    
    logger.info(
        f"[AssetCollection] Summary: {len(selected)} real assets selected "
        f"({video_count} videos, {image_count} images), "
        f"{len(set(ai_required))} visuals require AI generation"
    )
    
    return AssetCollectionResult(
        selected_assets=selected,
        ai_required_indices=sorted(set(ai_required)),
        issues=issues,
    )
