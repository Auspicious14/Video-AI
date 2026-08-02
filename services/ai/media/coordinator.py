"""
services/ai/media/coordinator.py — Media Engine Coordinator

Responsibility:
Orchestrates the entire Media Acquisition loop:
Topic -> Research -> Script -> Planner -> Cache -> Collector -> Ranker -> Downloader -> Classifier -> Renderer
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple, Optional
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw

from config import OUTPUT_DIR
from services.images import get_image_client
from services.ai.schemas import ResearchResult, ScriptResult, Scene, MediaPlan
from services.ai.media.planner import plan_script_media
from services.ai.media.collector import MediaCollector, MediaAsset
from services.ai.media.ranking import rank_assets
from services.ai.media.downloader import MediaDownloader
from services.ai.media.cache import MediaCache
from services.ai.media.classifier import classify_local_media
from services.ai.media.retrieval_orchestrator import RetrievalOrchestrator

logger = logging.getLogger(__name__)


def _create_simple_placeholder(output_path: Path, title: str) -> Path:
    """Generates a small black placeholder image to satisfy the renderer if needed."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (576, 1024), (18, 18, 20))
        draw = ImageDraw.Draw(img)
        # Draw simple text in center
        draw.text((20, 512), f"Loading: {title[:30]}", fill=(100, 100, 100))
        img.save(output_path, "JPEG", quality=90)
        return output_path
    except Exception as exc:
        logger.warning("Failed to construct simple PIL placeholder: %s", exc)
        return output_path


async def _generate_fallback_ai_image(
    scene: Scene,
    job_id: str,
    scene_idx: int,
    health_mode: bool = False
) -> Path:
    """Generates an AI Image using the standard provider waterfall as a fallback."""
    img_client = get_image_client()
    output_path = OUTPUT_DIR / f"{job_id}_scene_{scene_idx}_fallback.jpg"
    
    raw_prompt = scene.image_prompt or scene.description or "cinematic graphic"
    
    # Format and prepend framing hint
    if "9:16" not in raw_prompt and "vertical" not in raw_prompt.lower():
        full_prompt = (
            f"cinematic vertical 9:16 TikTok video frame, "
            f"ultra realistic, sharp focus, professional photography, "
            f"dramatic lighting, {raw_prompt}"
        )
    else:
        full_prompt = raw_prompt

    logger.info("[Coordinator] Generating AI Image fallback for scene %d...", scene_idx)
    try:
        await img_client.generate_image(
            prompt=full_prompt,
            output_path=str(output_path),
            width=1080,
            height=1920,
            scene_context=scene.description,
            health_mode=health_mode,
        )
        return output_path
    except Exception as exc:
        logger.error("[Coordinator] AI Image generation failed: %s. Using blank placeholder.", exc)
        return _create_simple_placeholder(output_path, scene.description)


async def acquire_media_assets(
    research: ResearchResult | dict,
    script: ScriptResult | dict,
    job_id: str,
    health_mode: bool = False,
) -> Tuple[List[Tuple[Path, float]], List[Optional[Path]]]:
    """
    Main entry point for media acquisition.
    
    Returns
    -------
    Tuple containing:
      1. image_paths: List[Tuple[Path, float]] (B-roll stills/backdrops for each scene + duration)
      2. ai_clip_paths: List[Optional[Path]] (Video source path or None for still-only scenes)
    """
    logger.info("Initializing Media Acquisition Engine for Job %s", job_id)

    # Coerce dictionary inputs to class schemas
    if isinstance(research, dict):
        research = ResearchResult.model_validate(research)
    if isinstance(script, dict):
        script = ScriptResult.model_validate(script)

    # 1. Planner Phase
    plans = await plan_script_media(research, script)

    
    retrieval = RetrievalOrchestrator()
    downloader = MediaDownloader()
    cache = MediaCache()

    image_paths: List[Tuple[Path, float]] = []
    ai_clip_paths: List[Optional[Path]] = []

    # Map plan list to 1-based scene indexes
    plan_by_scene = {p.scene: p for p in plans}

    for idx, scene in enumerate(script.scenes):
        scene_num = idx + 1
        duration = scene.duration
        plan = plan_by_scene.get(scene_num)
        
        if not plan:
            logger.warning("No media plan found for scene %d, using default fallback.", scene_num)
            plan = MediaPlan(
                scene=scene_num,
                media_type="ai_image",
                search_query=scene.image_prompt,
                reasoning="Default fallback",
                fallback_media_type="stock_video",
                confidence=0.5
            )

        logger.info(
            "Scene %d | Plan type: %s | Query: %r",
            scene_num, plan.preferred_asset_kind, plan.visual_intent.search_query
        )

        local_media_path: Optional[Path] = None
        media_is_video = False

        # If planner requested AI image directly, skip search & download
        if plan.preferred_asset_kind.lower() == "ai_image":
            logger.info("Plan explicitly requested AI image for scene %d.", scene_num)
            local_media_path = await _generate_fallback_ai_image(scene, job_id, idx, health_mode)
        else:
            # Check Media Cache first
            cached_path = cache.get(
                plan.visual_intent.search_query,
                plan.visual_intent.preferred_asset_kind,
            )
            if cached_path:
                local_media_path = cached_path
                # Check if it was classified as a video
                meta = classify_local_media(local_media_path)
                media_is_video = meta.get("is_video", False)
            else:
                # Cache miss, Search and Collect Candidates
                intent = plan.visual_intent
                
                # Filter/rank candidates
                candidates = await retrieval.retrieve(
                    intent,
                    limit=8,
                )

                
                # Attempt to download the best ranked asset
                download_success = False
                for asset in candidates:
                    try:
                        downloaded = downloader.download(asset)
                        
                        # Validate structure
                        meta = classify_local_media(
                            downloaded.local_path
                        )
                        if meta.get("exists") and not meta.get("error"):
                            local_media_path = downloaded.local_path
                            media_is_video = meta.get("is_video", False)
                            download_success = True
                            
                            # Cache the result
                            cache.set(
                                intent.search_query,
                                intent.preferred_asset_kind,
                                downloaded.local_path,
                            )
                            break
                    except Exception as e:
                        logger.warning("Failed to acquire asset option from %s: %s. Trying next option.", asset.provider, e)
                
                if not download_success:
                    logger.warning("Could not acquire any real assets for scene %d. Falling back to AI Image generation.", scene_num)
                    local_media_path = await _generate_fallback_ai_image(scene, job_id, idx, health_mode)

        # 4. Integrate with video outputs
        if media_is_video:
            # Selected asset is a video clip!
            ai_clip_paths.append(local_media_path)
            
            # Place a dummy background image for satisfying composition validation
            placeholder_path = OUTPUT_DIR / f"{job_id}_scene_{idx}_bg_placeholder.jpg"
            if not placeholder_path.exists():
                _create_simple_placeholder(placeholder_path, scene.description)
            
            image_paths.append((placeholder_path, duration))
        else:
            # Selected asset is an image!
            ai_clip_paths.append(None)
            image_paths.append((local_media_path, duration))

    logger.info("Successfully acquired media assets: %d images, %d motion clips.", len(image_paths), sum(1 for c in ai_clip_paths if c is not None))
    return image_paths, ai_clip_paths
