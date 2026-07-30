"""Stage 6 and 8: visual planning specialists."""

from __future__ import annotations

import logging

from services.ai.exceptions import ValidationError
from services.ai.schemas import ImageGenerationPlanResult, ScriptQAResult, VisualPlanResult
from services.ai.studio.agent_utils import generate_structured_artifact
from services.ai.studio.context import (
    ImageGenerationContext,
    VisualPlanningContext,
    script_context,
    visual_plan_context,
    VisualTimelineItem
)

logger = logging.getLogger(__name__)


def _validate_and_repair_timeline_duration(
    visual_plan: VisualPlanResult,
    target_duration: int,
) -> VisualPlanResult:
    """
    Ensure the visual timeline covers the full target duration.
    
    Checks:
    - Timeline starts at 0.0
    - Timeline ends at target_duration (±2% tolerance)
    - No gaps between items
    
    Repairs:
    - Scales timeline proportionally if duration is off
    - Adjusts first item to start at 0.0
    - Adjusts last item to end at target_duration
    - Splits long beats for documentary pacing
    """
    if not visual_plan.timeline:
        logger.warning("Visual plan has empty timeline")
        return visual_plan
    
    # First, improve pacing by splitting long beats
    visual_plan.timeline = _improve_documentary_pacing(visual_plan.timeline, target_duration)    
    # Check current timeline duration
    first_start = visual_plan.timeline[0].start_seconds
    last_end = visual_plan.timeline[-1].end_seconds
    current_duration = last_end - first_start
    
    tolerance = target_duration * 0.02  # 2% tolerance
    
    # If timeline is within tolerance, only adjust edges
    if abs(current_duration - target_duration) <= tolerance:
        visual_plan.timeline[0].start_seconds = 0.0
        visual_plan.timeline[-1].end_seconds = float(target_duration)
        return visual_plan
    
    # Timeline is significantly off - need to scale
    if current_duration <= 0:
        logger.warning(f"Invalid timeline duration: {current_duration}s, cannot scale")
        return visual_plan
    
    scale_factor = target_duration / current_duration
    logger.info(
        f"Scaling visual timeline from {current_duration:.1f}s to {target_duration}s "
        f"(scale={scale_factor:.3f})"
    )
    
    # Scale all timing
    for item in visual_plan.timeline:
        # Offset to start from 0, then scale
        relative_start = item.start_seconds - first_start
        relative_end = item.end_seconds - first_start
        item.start_seconds = round(relative_start * scale_factor, 2)
        item.end_seconds = round(relative_end * scale_factor, 2)
    
    # Final adjustment to ensure exact boundaries
    visual_plan.timeline[0].start_seconds = 0.0
    visual_plan.timeline[-1].end_seconds = float(target_duration)
    
    return visual_plan


def _improve_documentary_pacing(
    timeline: list[VisualTimelineItem],
    target_duration: int | None = None,
) -> list[VisualTimelineItem]:
    """
    Split long visual beats into documentary-style cuts.

    Only applies to long-form content. For short test/preset videos, splitting
    every beat over 8s fragments a handful of narrative beats into dozens of
    tiny cuts — which both reads as redundant (Final QA already flags this)
    and quietly shortens the render, since each crossfade transition between
    chained clips overlaps by transition_duration, so more cuts means more
    total seconds lost to overlap.
    """
    if target_duration is not None and target_duration <= 180:
        return timeline

    MAX_BEAT_DURATION = 8.0
    IDEAL_CUT_INTERVAL = 4.0
    
    improved_timeline = []
    
    for item in timeline:
        duration = item.end_seconds - item.start_seconds
        
        # Short beats are fine as-is
        if duration <= MAX_BEAT_DURATION:
            improved_timeline.append(item)
            continue
        
        # Calculate how many cuts we need
        num_cuts = max(2, int(duration / IDEAL_CUT_INTERVAL))
        cut_duration = duration / num_cuts
        
        # Create B-roll cuts from the same visual concept
        # Documentary pattern: wide shot → medium shot → close-up → detail
        cut_patterns = [
            ("wide shot", "slow zoom in"),
            ("medium shot", "slow pan right"),
            ("close-up detail", "static hold"),
            ("alternative angle", "slow pan left"),
        ]
        
        for i in range(num_cuts):
            pattern_idx = i % len(cut_patterns)
            cut_description, motion = cut_patterns[pattern_idx]
            
            cut_item = item.model_copy(deep=True)
            cut_item.start_seconds = round(item.start_seconds + (i * cut_duration), 2)
            cut_item.end_seconds = round(item.start_seconds + ((i + 1) * cut_duration), 2)
            
            # Vary the visual description for different cuts
            if i == 0:
                # First cut keeps original description
                pass
            else:
                # Subsequent cuts are variations
                cut_item.on_screen = f"{item.on_screen} - {cut_description}"
                cut_item.motion_direction = motion
                cut_item.reason = f"B-roll cut {i+1}/{num_cuts} for pacing"
            
            improved_timeline.append(cut_item)
    
    # Re-index the timeline
    for idx, item in enumerate(improved_timeline):
        item.index = idx
    
    return improved_timeline


async def run_visual_planning_agent(
    *,
    context: VisualPlanningContext,
) -> VisualPlanResult:
    """
    Create the visual timeline before images are generated.
    
    Optimized: Receives minimal context (2,000 tokens) instead of full artifacts (5,500 tokens).
    Token reduction: 64%
    
    Note: Narration is required (1,800 tokens) - visual planner must align to spoken words.
    """
    # Token budget: ~100 tokens per beat, ~1 beat per 7s, plus 300 overhead.
    # Mistral free tier caps at 4096 output; leaving 800 for prompt means
    # we must stay well under 3200.  Cap at 2600 to be safe across providers.
    max_beats = max(5, context.target_duration // 7)
    token_budget = min(2600, max(900, max_beats * 110 + 300))

    result = await generate_structured_artifact(
        prompt_name="studio_visual_planner",
        model=VisualPlanResult,
        variables={
            "target_duration": context.target_duration,
            "aspect_ratio": context.aspect_ratio,
            "narration": context.narration,
            "max_beats": max_beats,
            "sections": (
                "\n".join(
                    f"  - {t['start_seconds']:.1f}-{t['end_seconds']:.1f}s "
                    f"[{t['title']}, ~{t['word_count']} words]"
                    for t in context.section_timings
                )
                if context.section_timings
                else "\n".join(f"  - {section}" for section in context.sections)
            ),
        },
        temperature=0.42,
        max_tokens=token_budget,
    )
    
    # Validate and repair timeline duration alignment
    return _validate_and_repair_timeline_duration(result, context.target_duration)


async def run_image_generation_planner_agent(
    *,
    context: ImageGenerationContext | None = None,
    visual_plan: VisualPlanResult | None = None,
    ai_required_indices: list[int] | None = None,
) -> ImageGenerationPlanResult:
    """
    Produce cinematic AI prompts only for beats without suitable real assets.
    
    Optimized: Receives only AI-required visuals (3,000 tokens) instead of full timeline (18,000 tokens).
    Token reduction: 83%
    
    This is the largest single optimization in the pipeline.
    """
    if context is None:
        if visual_plan is None:
            raise ValueError("context or visual_plan is required for image generation planning")
        wanted = set(ai_required_indices or [])
        context = ImageGenerationContext(
            style_reference=visual_plan.visual_style,
            required_visuals=[item for item in visual_plan.timeline if item.index in wanted],
        )

    if not context.required_visuals:
        return ImageGenerationPlanResult(
            style_reference=context.style_reference,
            prompts=[],
        )

    try:
        # Build minimal visual plan context with only required items
        visual_context_lines = [f"VISUAL STYLE: {context.style_reference}", "REQUIRED VISUALS:"]
        for item in context.required_visuals:
            visual_context_lines.append(
                f"  {item.index}. {item.start_seconds:.1f}-{item.end_seconds:.1f}s "
                f"[{item.asset_type.value}] {item.on_screen}"
            )
        visual_context = "\n".join(visual_context_lines)
        
        result = await generate_structured_artifact(
            prompt_name="studio_image_generation",
            model=ImageGenerationPlanResult,
            variables={
                "visual_plan_context": visual_context,
                "ai_required_indices": ", ".join(str(item.index) for item in context.required_visuals),
                "style_reference": context.style_reference,
            },
            temperature=0.42,
            max_tokens=2200,  # Phase 2A: Realistic limit for image gen plan (~1800 tokens typical)
            attempts=2,
        )
        repaired_by_index = {item.index: item for item in result.prompts}
        merged = []
        for item in context.required_visuals:
            generated = repaired_by_index.get(item.index)
            if generated:
                if not generated.narration_reference:
                    generated.narration_reference = item.narration_reference
                if not generated.on_screen:
                    generated.on_screen = item.on_screen
                if not generated.generation_prompt:
                    generated.generation_prompt = item.generation_prompt or item.on_screen
                merged.append(generated)
            else:
                # Use context.style_reference, not visual_plan.visual_style (visual_plan may be None)
                merged.append(_fallback_prompt_item(item, context.style_reference))
        result.prompts = merged
        return result
    except ValidationError as exc:
        logger.warning(
            "Image generation planner output failed; deriving prompts from visual plan | error=%s",
            exc,
        )
        return ImageGenerationPlanResult(
            style_reference=context.style_reference,
            prompts=[
                _fallback_prompt_item(item, context.style_reference)
                for item in context.required_visuals
            ],
        )


def _fallback_prompt_item(item, style_reference: str):
    """Create a complete AI prompt item from an existing visual timeline beat."""
    prompt = item.generation_prompt or item.on_screen
    if style_reference and style_reference.lower() not in prompt.lower():
        prompt = f"{prompt}, {style_reference}"
    if "cinematic" not in prompt.lower():
        prompt = f"cinematic documentary frame, {prompt}"

    updated = item.model_copy(deep=True)
    updated.sourcing_priority = "ai_only"
    updated.generation_prompt = (
        f"{prompt}, realistic lighting, coherent composition, no fake logos, no unreadable text"
    )
    return updated
