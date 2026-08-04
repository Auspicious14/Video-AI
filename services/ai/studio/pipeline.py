"""End-to-end AI-first YouTube production studio pipeline."""

from __future__ import annotations
from services.ai.studio import script_qa
from pydantic import warnings
import logging
from pathlib import Path
from typing import Any
from config import OUTPUT_DIR
from models import YouTubeStudioRequest
from services.ai.research import PLATFORM_YT_LONG, run_research
from services.ai.schemas import (
    AudioQAResult,
    DocumentaryScriptResult,
    EditingPlanResult,
    FinalQAResult,
    ImageGenerationPlanResult,
    QualityIssue,
    ResearchResult,
    ScriptQAResult,
    SEOResult,
    StoryArchitectureResult,
    ThumbnailStrategyResult,
    TitleStrategyResult,
    TopicIntelligenceResult,
    VisualPlanResult,
    VoiceDirectionResult,
    YouTubeProductionPackage,
)
from services.ai.studio.asset_collection import run_asset_collection_service
from services.ai.studio.cache import get_or_create_artifact
from services.ai.studio.context import (
    build_image_generation_context,
    build_seo_context,
    build_thumbnail_context,
    build_title_context,
    build_visual_planning_context,
    build_voice_direction_context,
)
from services.ai.studio.editing import run_editing_plan_agent
from services.ai.studio.packaging import (
    run_final_qa_agent,
    run_thumbnail_strategy_agent,
    run_title_strategy_agent,
    run_youtube_seo_agent,
)
from services.ai.studio.script_qa import run_script_qa_agent
from services.ai.studio.script_writer import run_documentary_script_writer_agent
from services.ai.studio.story_architect import run_story_architect_agent
from services.ai.studio.topic_intelligence import run_topic_intelligence_agent
from services.ai.studio.visual_planner import (
    run_image_generation_planner_agent,
    run_visual_planning_agent,
)
from services.ai.studio.voice_director import run_audio_qa, run_voice_direction_agent
from services.audio import generate_audio, get_audio_duration
import store
from services.thumbnail import render_thumbnail_for_job

logger = logging.getLogger(__name__)


def _set_stage(job_id: str, status: str, detail: str, progress: int, **extra: Any) -> None:
    store.update_job(
        job_id,
        status=status,
        status_detail=detail,
        progress=progress,
        **extra,
    )


def _artifact_file(job_id: str, name: str) -> Path:
    return OUTPUT_DIR / f"{job_id}_{name}.json"


def _save_job_artifact(job_id: str, name: str, artifact: Any) -> None:
    if hasattr(artifact, "model_dump"):
        data = artifact.model_dump(mode="json")
        text = artifact.model_dump_json(indent=2)
    else:
        data = artifact
        import json

        text = json.dumps(artifact, indent=2, default=str)
    _artifact_file(job_id, name).write_text(text, encoding="utf-8")
    store.update_job(job_id, artifacts={**(store.get_job(job_id) or {}).get("artifacts", {}), name: data})


def _build_subtitle_lines(narration: str, total_duration: float, words_per_card: int = 7) -> list[tuple[str, float, float]]:
    """Build timed subtitle cards, sized proportionally by each card's length
    rather than assuming every card takes equal time to speak. A short card
    and a long card at equal duration is exactly what causes captions to
    race ahead of or lag behind the actual narration."""
    words = narration.split()
    if not words or total_duration <= 0:
        return []

    cards = [" ".join(words[i:i + words_per_card]) for i in range(0, len(words), words_per_card)]
    weights = [max(1, len(card)) for card in cards]
    total_weight = sum(weights)

    lines: list[tuple[str, float, float]] = []
    cursor = 0.0
    for text, weight in zip(cards, weights):
        duration = total_duration * (weight / total_weight)
        lines.append((text, round(cursor, 3), round(cursor + duration, 3)))
        cursor += duration
    return lines

async def _render_studio_video(
    *,
    job_id: str,
    req: YouTubeStudioRequest,
    script_qa: ScriptQAResult,
    visual_plan: VisualPlanResult,
    audio_path: Path,
    actual_duration: float,
    generated_images: list[dict[str, Any]],
    thumbnail_path: Path | None = None,  
) -> tuple[Path, list[str]]:
    """Render a YouTube Studio production using local or generated timeline frames."""
    from services.images import get_image_client
    from services.renderer import dimensions_for_aspect_ratio, render_video

    width, height = dimensions_for_aspect_ratio(req.aspect_ratio)

    # Build lookup table for existing visual assets
    # Prefer: downloaded real assets (especially videos) > AI generated images
    existing: dict[int, tuple[Path, str]] = {}  # visual_index -> (path, asset_type)

    for item in generated_images:
        if item.get("local_path") and Path(item["local_path"]).exists():
            status = item.get("status")
            if status in {"downloaded", "generated"}:
                visual_idx = item["visual_index"]
                asset_path = Path(item["local_path"])
                asset_type = item.get("asset_type", "")

                should_use = True
                if visual_idx in existing:
                    current_path, current_type = existing[visual_idx]
                    is_video = "video" in asset_type.lower()
                    current_is_video = "video" in current_type.lower()

                    if current_is_video and not is_video:
                        should_use = False
                    elif is_video and not current_is_video:
                        should_use = True
                    elif status == "downloaded" and item.get("source") != "ai":
                        should_use = True

                if should_use:
                    existing[visual_idx] = (asset_path, asset_type)
                    logger.info(
                        f"[Renderer] Visual {visual_idx}: Using {status} {asset_type} "
                        f"from {item.get('source', 'unknown')}: {asset_path.name}"
                    )

    image_client = get_image_client()
    image_paths: list[tuple[Path, float]] = []
    ai_clip_paths: list[Path | None] = []
    warnings: list[str] = []
    last_frame: Path | None = None
    last_frame_is_video = False

    raw_durations = [
        max(1.0, item.end_seconds - item.start_seconds)
        for item in visual_plan.timeline
    ]
    TRANSITION_DURATION = 0.4  # must match render_video()'s default in renderer.py
    transition_overhead = max(0, len(raw_durations) - 1) * TRANSITION_DURATION
    scale = (
        (actual_duration + transition_overhead) / sum(raw_durations)
        if raw_durations and actual_duration > 0
        else 1.0
    )

    for item, raw_duration in zip(visual_plan.timeline, raw_durations):
        frame_info = existing.get(item.index)
        frame_path = frame_info[0] if frame_info else None
        is_video = bool(frame_info) and "video" in frame_info[1].lower()

        if frame_path is None:
            logger.warning(
                f"[Renderer] Visual {item.index}: No downloaded or generated asset found. "
                f"Falling back to AI image generation."
            )
            frame_path = OUTPUT_DIR / f"{job_id}_studio_render_{item.index}.jpg"
            prompt = item.generation_prompt or item.on_screen
            is_video = False  # AI fallback images are always stills
            try:
                await image_client.generate_image(
                    prompt=prompt,
                    output_path=str(frame_path),
                    width=width,
                    height=height,
                )
                logger.info(f"[Renderer] Visual {item.index}: Generated AI fallback image")
            except Exception as exc:  # noqa: BLE001
                if last_frame is None:
                    warnings.append(f"Used deterministic fallback for visual {item.index}: {exc}")
                    logger.warning(f"[Renderer] Visual {item.index}: no prior frame — using deterministic fallback")
                    from services.renderer import create_fallback_frame
                    frame_path = create_fallback_frame(
                        item.on_screen or "…",
                        OUTPUT_DIR / f"{job_id}_fallback_{item.index}.png",
                        width, height,
                    )
                    is_video = False

        duration = round(raw_duration * scale, 3)
        image_paths.append((frame_path, duration))
        ai_clip_paths.append(frame_path if is_video else None)
        last_frame = frame_path
        last_frame_is_video = is_video
    # in _render_studio_video, right before "if not image_paths: raise ..."
    total_planned = sum(d for _, d in image_paths)
    if total_planned < actual_duration * 0.95:
        logger.error(
            f"[Renderer] Planned visual duration ({total_planned:.1f}s) is significantly "
            f"short of narration duration ({actual_duration:.1f}s) — video will be shorter "
            f"than the audio. Warnings so far: {warnings}"
        )
    if not image_paths:
        raise RuntimeError("No local or generated visual frames are available for studio render.")
    if thumbnail_path and thumbnail_path.exists():
        THUMBNAIL_DURATION = 1.0

    if thumbnail_path and thumbnail_path.exists():
        image_paths.insert(0, (thumbnail_path, THUMBNAIL_DURATION))
        ai_clip_paths.insert(0, None)

        actual_duration += THUMBNAIL_DURATION

        logger.info(
            "[Renderer] Added thumbnail intro (%.1fs): %s",
            THUMBNAIL_DURATION,
            thumbnail_path.name,
        )

    script_meta = {
        "hook": script_qa.revised_script.hook,
        "cta": "Subscribe for more documentary stories.",
    }
    subtitle_lines = _build_subtitle_lines(script_qa.revised_script.narration, actual_duration)
    video_path = await render_video(
        audio_path=audio_path,
        image_paths=image_paths,
        ai_clip_paths=ai_clip_paths,
        script=script_meta,
        job_id=job_id,
        actual_duration=actual_duration,
        subtitle_lines=subtitle_lines,
        aspect_ratio=req.aspect_ratio,
    )
    return video_path, warnings

async def run_youtube_studio_production(job_id: str, req: YouTubeStudioRequest) -> None:
    """
    Build a full documentary-style production package from a single topic.

    The concrete media generation steps are optional and fault-tolerant. Even if
    audio/image providers fail, the production package and final QA still report
    what is ready and what needs manual attention.
    """
    try:
        topic = req.topic.strip()
        target_duration = req.resolved_duration

        # Stage 1
        _set_stage(job_id, "topic_intelligence", "Building content brief...", 5)
        brief = await get_or_create_artifact(
            stage="topic_intelligence",
            payload={
                "topic": topic,
                "audience_profile": req.audience_profile,
                "target_platform": "youtube",
                "monetization_goal": req.monetization_goal,
            },
            model=TopicIntelligenceResult,
            factory=lambda: run_topic_intelligence_agent(
                topic=topic,
                audience_profile=req.audience_profile,
                monetization_goal=req.monetization_goal,
            ),
        )
        _save_job_artifact(job_id, "topic_intelligence", brief)

        # Stage 2
        _set_stage(job_id, "researching", "Researching once for all downstream agents...", 12)
        research = await get_or_create_artifact(
            stage="research",
            payload={
                "topic": topic,
                "tone": req.tone,
                "duration": target_duration,
                "platform": PLATFORM_YT_LONG,
                "audience_profile": req.audience_profile,
                "brief": brief.model_dump(mode="json"),
            },
            model=ResearchResult,
            factory=lambda: run_research(
                topic=topic,
                tone=req.tone,
                duration=target_duration,
                platform=PLATFORM_YT_LONG,
                audience_profile=req.audience_profile or brief.target_audience,
            ),
        )
        _save_job_artifact(job_id, "research", research)

        # Stage 3
        _set_stage(job_id, "story_architecture", "Designing the documentary story...", 20)
        story = await get_or_create_artifact(
            stage="story_architecture",
            payload={
                "brief": brief.model_dump(mode="json"),
                "research": research.model_dump(mode="json"),
                "target_duration": target_duration,
            },
            model=StoryArchitectureResult,
            factory=lambda: run_story_architect_agent(
                brief=brief,
                research=research,
                target_duration=target_duration,
            ),
        )
        _save_job_artifact(job_id, "story", story)

        # Stage 4
        _set_stage(job_id, "script_writing", "Writing narration from approved story architecture...", 30)
        script = await get_or_create_artifact(
            stage="script_writing",
            payload={
                "brief": brief.model_dump(mode="json"),
                "research": research.model_dump(mode="json"),
                "story": story.model_dump(mode="json"),
                "target_duration": target_duration,
            },
            model=DocumentaryScriptResult,
            factory=lambda: run_documentary_script_writer_agent(
                brief=brief,
                research=research,
                story=story,
                target_duration=target_duration,
            ),
        )
        _save_job_artifact(job_id, "script", script)

        # Stage 5
        _set_stage(job_id, "script_qa", "Reviewing and revising script quality...", 38)
        script_qa = await get_or_create_artifact(
            stage="script_qa",
            payload={
                "script": script.model_dump(mode="json"),
                "research": research.model_dump(mode="json"),
                "story": story.model_dump(mode="json"),
                "target_duration": target_duration,
            },
            model=ScriptQAResult,
            factory=lambda: run_script_qa_agent(
                script=script,
                research=research,
                story=story,
                target_duration=target_duration,
            ),
        )
        _save_job_artifact(job_id, "script_qa", script_qa)

        # Stage 6
        _set_stage(job_id, "visual_planning", "Planning on-screen visuals before generation...", 48)
        
        # Build minimal context for visual planner (64% token reduction)
        visual_planning_ctx = build_visual_planning_context(
            script_qa=script_qa,
            target_duration=target_duration,
            aspect_ratio=req.aspect_ratio,
        )
        
        visual_plan = await get_or_create_artifact(
            stage="visual_planning",
            payload={
                "script_qa": script_qa.model_dump(mode="json"),
                "target_duration": target_duration,
                "aspect_ratio": req.aspect_ratio,
            },
            model=VisualPlanResult,
            factory=lambda: run_visual_planning_agent(context=visual_planning_ctx),
        )
        _save_job_artifact(job_id, "visual_plan", visual_plan)

        # Stage 7
        _set_stage(job_id, "asset_collection", "Collecting real assets where possible...", 56)
        asset_collection = await run_asset_collection_service(visual_plan=visual_plan)
        _save_job_artifact(job_id, "asset_collection", asset_collection)

        # Stage 7.5: Download selected real assets
        _set_stage(job_id, "asset_download", "Downloading selected real assets...", 59)
        downloaded_assets: list[dict[str, Any]] = []
        
        if asset_collection.selected_assets:
            from services.ai.media.downloader import MediaDownloader
            from services.ai.media.asset import MediaAsset
            from services.ai.media.asset_types import AssetKind
            
            downloader = MediaDownloader()
            
            for candidate in asset_collection.selected_assets:
                try:
                    # Convert AssetCandidate to MediaAsset for downloader
                    media_asset = MediaAsset(
                        url=candidate.url,
                        kind=AssetKind(candidate.asset_type),
                        provider=candidate.source,
                        provider_id=f"{candidate.source}_{candidate.visual_index}_{candidate.asset_index}",
                        title=candidate.credit or f"Asset {candidate.visual_index}",
                    )
                    
                    logger.info(
                        f"[Pipeline] Downloading asset for visual {candidate.visual_index} "
                        f"from {candidate.source}: {candidate.asset_type}"
                    )
                    
                    local_asset = downloader.download(media_asset)
                    
                    # Update candidate's local_path
                    candidate.local_path = str(local_asset.local_path)
                    
                    # Add to downloaded_assets list (similar structure to generated_images)
                    downloaded_assets.append({
                        "visual_index": candidate.visual_index,
                        "local_path": str(local_asset.local_path),
                        "status": "downloaded",
                        "source": candidate.source,
                        "asset_type": candidate.asset_type,
                        "url": candidate.url,
                    })
                    
                    logger.info(
                        f"[Pipeline] ✓ Downloaded visual {candidate.visual_index}: "
                        f"{local_asset.local_path.name} ({local_asset.local_path.stat().st_size:,} bytes)"
                    )
                    
                except Exception as exc:
                    logger.error(
                        f"[Pipeline] Failed to download asset for visual {candidate.visual_index} "
                        f"from {candidate.source}: {exc}. Will fall back to AI generation."
                    )
                    # Mark this visual for AI generation fallback
                    if candidate.visual_index not in asset_collection.ai_required_indices:
                        asset_collection.ai_required_indices.append(candidate.visual_index)
                    
                    downloaded_assets.append({
                        "visual_index": candidate.visual_index,
                        "status": "failed",
                        "error": str(exc),
                        "source": candidate.source,
                    })
        
        _save_job_artifact(job_id, "downloaded_assets", downloaded_assets)
        logger.info(f"[Pipeline] Downloaded {len([a for a in downloaded_assets if a.get('status') == 'downloaded'])} real assets")

        # Stage 8
        _set_stage(job_id, "image_generation_plan", "Preparing AI image prompts for fallback beats...", 62)
        
        # Build minimal context for image generation (83% token reduction - largest win!)
        image_gen_ctx = build_image_generation_context(
            visual_plan=visual_plan,
            ai_required_indices=asset_collection.ai_required_indices,
        )
        
        image_generation_plan = await get_or_create_artifact(
            stage="image_generation_plan",
            payload={
                "visual_plan": visual_plan.model_dump(mode="json"),
                "ai_required": asset_collection.ai_required_indices,
            },
            model=ImageGenerationPlanResult,
            factory=lambda: run_image_generation_planner_agent(context=image_gen_ctx),
        )
        _save_job_artifact(job_id, "image_generation_plan", image_generation_plan)

        generated_images: list[dict[str, Any]] = []
        if req.generate_images and image_generation_plan.prompts:
            _set_stage(job_id, "image_generation", "Generating planned AI fallback images...", 65)
            from services.images import get_image_client

            image_client = get_image_client()
            width, height = (1920, 1080) if req.aspect_ratio == "16:9" else (1080, 1920)
            if req.aspect_ratio == "1:1":
                width = height = 1080

            for item in image_generation_plan.prompts:
                output_path = OUTPUT_DIR / f"{job_id}_studio_visual_{item.index}.jpg"
                prompt = item.generation_prompt or item.on_screen
                try:
                    await image_client.generate_image(
                        prompt=prompt,
                        output_path=str(output_path),
                        width=width,
                        height=height,
                    )
                    generated_images.append(
                        {
                            "visual_index": item.index,
                            "local_path": str(output_path),
                            "status": "generated",
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Studio image generation failed | job=%s visual=%s error=%s", job_id, item.index, exc)
                    generated_images.append(
                        {
                            "visual_index": item.index,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
            _save_job_artifact(job_id, "generated_images", generated_images)

        # Stage 9 and 10
        _set_stage(job_id, "voice_generation", "Directing and generating narration...", 68)
        voice_direction = await get_or_create_artifact(
            stage="voice_direction",
            payload={"script_qa": script_qa.model_dump(mode="json"), "voice_id": req.voice_id},
            model=VoiceDirectionResult,
            factory=lambda: run_voice_direction_agent(
                context=build_voice_direction_context(script_qa=script_qa, voice_id=req.voice_id)
            ),
        )
        _save_job_artifact(job_id, "voice_direction", voice_direction)

        audio_qa: AudioQAResult | None = None
        audio_path: Path | None = None
        if req.generate_audio:
            try:
                audio_path = await generate_audio(
                    narration=script_qa.revised_script.narration,
                    job_id=job_id,
                    voice_id=voice_direction.preferred_voice_id or req.voice_id,
                )
                audio_duration = get_audio_duration(audio_path)
                audio_qa = run_audio_qa(
                    audio_path=audio_path,
                    duration_seconds=audio_duration,
                    expected_duration_seconds=target_duration,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Studio audio generation failed | job=%s", job_id)
                audio_qa = AudioQAResult(
                    approved=False,
                    score=0,
                    duration_seconds=0,
                    issues=[
                        QualityIssue(
                            severity="critical",
                            stage="audio_qa",
                            issue=f"Audio generation failed: {exc}",
                            recommendation="Retry with another TTS provider or manually upload narration.",
                        )
                    ],
                )
            _save_job_artifact(job_id, "audio_qa", audio_qa)
            if audio_path:
                store.update_job(job_id, audio_url=f"/outputs/{audio_path.name}")

        # Stage 11
        _set_stage(job_id, "video_editing_plan", "Planning edit rhythm, motion, captions, and transitions...", 76)
        editing_plan = await get_or_create_artifact(
            stage="editing_plan",
            payload={
                "script_qa": script_qa.model_dump(mode="json"),
                "visual_plan": visual_plan.model_dump(mode="json"),
                "aspect_ratio": req.aspect_ratio,
            },
            model=EditingPlanResult,
            factory=lambda: run_editing_plan_agent(
                script_qa=script_qa,
                visual_plan=visual_plan,
                aspect_ratio=req.aspect_ratio,
            ),
        )
        _save_job_artifact(job_id, "editing_plan", editing_plan)

        # Stages 12-14
        _set_stage(job_id, "packaging", "Generating thumbnails, titles, and SEO metadata...", 84)
        thumbnails = await get_or_create_artifact(
            stage="thumbnail_strategy",
            payload={"research": research.model_dump(mode="json"), "script_qa": script_qa.model_dump(mode="json")},
            model=ThumbnailStrategyResult,
            factory=lambda: run_thumbnail_strategy_agent(
                context=build_thumbnail_context(research=research, script_qa=script_qa)
            ),
        )

        thumbnail_path = await render_thumbnail_for_job(
            job_id=job_id, topic=topic, thumbnails=thumbnails, output_dir=OUTPUT_DIR,
        )
        if thumbnail_path:
            store.update_job(job_id, thumbnail_url=f"/outputs/{thumbnail_path.name}")

        titles = await get_or_create_artifact(
            stage="title_strategy",
            payload={"research": research.model_dump(mode="json"), "script_qa": script_qa.model_dump(mode="json")},
            model=TitleStrategyResult,
            factory=lambda: run_title_strategy_agent(
                context=build_title_context(research=research, script_qa=script_qa)
            ),
        )

        seo = await get_or_create_artifact(
            stage="youtube_seo",
            payload={
                "research": research.model_dump(mode="json"),
                "script_qa": script_qa.model_dump(mode="json"),
                "topic": topic,
                "tone": req.tone,
            },
            model=SEOResult,
            factory=lambda: run_youtube_seo_agent(
                context=build_seo_context(topic=topic, tone=req.tone, research=research, script_qa=script_qa)
            ),
)
        _save_job_artifact(job_id, "thumbnails", thumbnails)
        _save_job_artifact(job_id, "titles", titles)
        _save_job_artifact(job_id, "seo", seo)

        # Stage 15
        _set_stage(job_id, "final_qa", "Running final production quality gate...", 93)
        final_qa = await get_or_create_artifact(
            stage="final_qa",
            payload={
                "research": research.model_dump(mode="json"),
                "script_qa": script_qa.model_dump(mode="json"),
                "visual_plan": visual_plan.model_dump(mode="json"),
                "asset_collection": asset_collection.model_dump(mode="json"),
                "audio_qa": audio_qa.model_dump(mode="json") if audio_qa else None,
                "editing_plan": editing_plan.model_dump(mode="json"),
                "thumbnails": thumbnails.model_dump(mode="json"),
                "titles": titles.model_dump(mode="json"),
                "seo": seo.model_dump(mode="json"),
            },
            model=FinalQAResult,
            factory=lambda: run_final_qa_agent(
                research=research,
                script_qa=script_qa,
                visual_plan=visual_plan,
                asset_collection=asset_collection,
                audio_qa=audio_qa,
                editing_plan=editing_plan,
                thumbnails=thumbnails,
                titles=titles,
                seo=seo,
            ),
        )

        package = YouTubeProductionPackage(
            topic_intelligence=brief,
            research=research,
            story=story,
            script_qa=script_qa,
            visual_plan=visual_plan,
            asset_collection=asset_collection,
            image_generation_plan=image_generation_plan,
            voice_direction=voice_direction,
            audio_qa=audio_qa,
            editing_plan=editing_plan,
            thumbnails=thumbnails,
            titles=titles,
            seo=seo,
            final_qa=final_qa,
        )
        package_path = OUTPUT_DIR / f"{job_id}_production_package.json"
        package_path.write_text(package.model_dump_json(indent=2), encoding="utf-8")

        warnings = [issue.issue for issue in final_qa.issues]
        video_url = None
        if req.render_video:
            if not audio_path or not audio_path.exists():
                warnings.append("Render requested, but narration audio is unavailable.")
            else:
                try:
                    _set_stage(job_id, "rendering", "Rendering long-form 16:9 studio video...", 96)
                    
                    # Merge downloaded real assets with AI-generated images
                    all_visual_assets = downloaded_assets + generated_images
                    
                    video_path, render_warnings = await _render_studio_video(
                        job_id=job_id,
                        req=req,
                        script_qa=script_qa,
                        visual_plan=visual_plan,
                        audio_path=audio_path,
                        actual_duration=audio_qa.duration_seconds if audio_qa else target_duration,
                        generated_images=all_visual_assets,  # Now includes both downloaded and generated
                        thumbnail_path=thumbnail_path,
                    )
                    video_url = f"/outputs/{video_path.name}"
                    warnings.extend(render_warnings)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Studio render failed | job=%s", job_id)
                    warnings.append(f"Studio render failed: {exc}")

        _set_stage(
            job_id,
            "done",
            "Production package ready.",
            100,
            package_url=f"/outputs/{package_path.name}",
            video_url=video_url,
            quality_score=final_qa.quality_score,
            warnings=warnings,
            title=titles.candidates[titles.best_index].title if titles.candidates else None,
        )
        logger.info("YouTube studio production complete | job=%s score=%.1f", job_id, final_qa.quality_score)

    except Exception as exc:
        store.update_job(
            job_id,
            status="failed",
            error=str(exc),
            status_detail=f"YouTube studio pipeline failed: {exc}",
            progress=0,
        )
        store.refund_credit(req.user_email)
        logger.exception("YouTube studio pipeline failed | job=%s error=%s", job_id, exc)
        raise
