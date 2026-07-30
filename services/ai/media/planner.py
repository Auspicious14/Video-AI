"""
services/ai/media/planner.py — Media Planner

Responsibility:
Analyze script scenes independently or as a batch to determine the best visual category, 
optimized search keywords, reasoning, fallback media types, and confidence scores.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from services.ai.client import generate_json
from services.ai.prompts import load_prompt
from services.ai.schemas import ResearchResult, ScriptResult, Scene, MediaPlan, MediaPlanResult
from services.ai.media.visual_intent import (
    VisualIntent,
    SubjectType,
    ShotType,
    CameraMotion,
    Emotion,
)
from services.ai.media.asset_types import AssetKind

logger = logging.getLogger(__name__)

# Valid media categories
VALID_MEDIA_TYPES = {
    "screenshot",
    "logo",
    "website",
    "product_image",
    "stock_video",
    "historical_photo",
    "chart",
    "map",
    "ai_image",
}


def _coerce_media_type(val: str, default: str = "ai_image") -> str:
    """Safely coerces unknown media types to stock_video or ai_image."""
    clean = val.strip().lower()
    # Handle minor singular/plural/space variations
    if clean in ("screenshots", "screenshot"):
        return "screenshot"
    if clean in ("logos", "logo", "brand"):
        return "logo"
    if clean in ("websites", "website", "webpage", "web"):
        return "website"
    if clean in ("product image", "product images", "product_images", "product_image", "product"):
        return "product_image"
    if clean in ("stock video", "stock videos", "stock_video", "stock_footage", "footage", "video"):
        return "stock_video"
    if clean in ("historical photo", "historical photos", "historical_photo", "historical", "archive"):
        return "historical_photo"
    if clean in ("charts", "chart", "graph", "diagram"):
        return "chart"
    if clean in ("maps", "map"):
        return "map"
    if clean in ("ai generated image", "ai image", "ai_image", "generator", "ai"):
        return "ai_image"
    
    return default


def _create_fallback_plan(scene_index: int, scene: Scene, reasoning: str = "Fallback due to planning error") -> MediaPlan:

    return MediaPlan(
        scene=scene_index,
        reasoning=reasoning,
        confidence=0.5,
        fallback_asset_kind=AssetKind.STOCK_IMAGE,
        visual_intent=VisualIntent(
            subject=scene.description[:80],
            subject_type=SubjectType.OBJECT,
            action="show",
            shot_type=ShotType.MEDIUM,
            motion=CameraMotion.STATIC,
            emotion=Emotion.CALM,
            search_keywords=[],
            preferred_sources=[],
            preferred_asset_kind=AssetKind.STOCK_IMAGE,
        ),
    )

async def plan_scene_media(
    research: ResearchResult,
    script: ScriptResult,
    scene: Scene,
    scene_index: int,
) -> MediaPlan:
    """
    Analyzes a single scene independently to determine the best visual category and search parameters.
    
    Returns
    -------
    MediaPlan
    """
    logger.info("Planning media for scene %d...", scene_index)
    
    research_summary = getattr(research, "executive_summary", "")
    if hasattr(research, "key_facts") and research.key_facts:
        research_summary += "\nKey Facts:\n" + "\n".join(f"- {f}" for f in research.key_facts[:5])

    try:
        system = load_prompt("base")
        prompt = load_prompt(
            "media_planner",
            topic=research.topic,
            tone=research.tone,
            duration=int(scene.duration),
            research_summary=research_summary,
            script_narration=script.narration,
            scene_index=scene_index,
            total_scenes=len(script.scenes),
            scene_description=scene.description,
            scene_narration=scene.narration,
        )

        raw = await generate_json(
            prompt=prompt,
            system=system,
            temperature=0.3,
            max_tokens=800,  # Phase 2A: Scene-level media plan (~600 tokens typical)
        )

        
        return MediaPlan.model_validate(raw)

    except Exception as exc:
        logger.error("Failed to plan media for scene %d: %s. Using default fallback.", scene_index, exc)
        return _create_fallback_plan(scene_index, scene, f"Fallback due to planning error: {exc}")


async def plan_script_media(
    research: ResearchResult,
    script: ScriptResult,
) -> List[MediaPlan]:
    """
    Batch-analyzes all scenes in a script together for context and speed efficiency.
    Falls back to scene-by-scene planning if the batch LLM call fails.
    
    Returns
    -------
    List[MediaPlan]
    """
    logger.info("Batch planning media for %d script scenes...", len(script.scenes))
    
    # Format scene dump for batch prompt
    scene_lines = []
    for idx, scene in enumerate(script.scenes, 1):
        scene_lines.append(
            f"Scene {idx}:\n"
            f"- Description: {scene.description}\n"
            f"- Narration: {scene.narration}\n"
            f"- Duration: {scene.duration}s"
        )
    scenes_dump = "\n\n".join(scene_lines)

    research_summary = getattr(research, "executive_summary", "")
    if hasattr(research, "key_facts") and research.key_facts:
        research_summary += "\nKey Facts:\n" + "\n".join(f"- {f}" for f in research.key_facts[:5])

    try:
        system = load_prompt("base")
        prompt = load_prompt(
            "media_planner_script",
            topic=research.topic,
            tone=research.tone,
            duration=int(sum(s.duration for s in script.scenes)),
            research_summary=research_summary,
            scenes_dump=scenes_dump,
        )

        raw = await generate_json(
            prompt=prompt,
            system=system,
            temperature=0.3,
            max_tokens=2400,  # Phase 2A: Script-level media plan (~1800 tokens typical)
        )

        # Validate structure via Pydantic model
        validated_result = MediaPlanResult.model_validate(raw)
        
        # Post-process and ensure correct scene matching
        plans = []
        plan_dict = {p.scene: p for p in validated_result.plans}
        
        for idx, scene in enumerate(script.scenes, 1):
            plan = plan_dict.get(idx)
            if plan:
                plans.append(plan)
            else:
                # Missing scene plan in LLM output, plan independently
                logger.warning("Scene %d missing in batch plan response, running individual planner", idx)
                ind_plan = await plan_scene_media(research, script, scene, idx)
                plans.append(ind_plan)

        return plans

    except Exception as exc:
        logger.warning("Batch script planning failed: %s. Falling back to scene-by-scene planning.", exc)
        # Fall back to scene-by-scene planning
        plans = []
        for idx, scene in enumerate(script.scenes, 1):
            plan = await plan_scene_media(research, script, scene, idx)
            plans.append(plan)
        return plans
