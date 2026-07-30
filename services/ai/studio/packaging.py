"""Stages 12-15: packaging, SEO, and final QA specialists."""

from __future__ import annotations

from services.ai.schemas import (
    AssetCollectionResult,
    AudioQAResult,
    EditingPlanResult,
    FinalQAResult,
    ResearchResult,
    ScriptQAResult,
    SEOResult,
    ThumbnailStrategyResult,
    TitleStrategyResult,
    VisualPlanResult,
)
from services.ai.seo import run_seo_agent
from services.ai.studio.agent_utils import generate_structured_artifact
from services.ai.studio.context import (
    SEOContext,
    ThumbnailContext,
    TitleContext,
    research_brief_context,
    script_context,
    visual_plan_context,
)


async def run_thumbnail_strategy_agent(
    *,
    context: ThumbnailContext,
) -> ThumbnailStrategyResult:
    """
    Generate scored thumbnail concepts.
    
    Optimized: Receives minimal context (400 tokens) instead of full artifacts (4,500 tokens).
    Token reduction: 91%
    """
    return await generate_structured_artifact(
        prompt_name="studio_thumbnail_strategy",
        model=ThumbnailStrategyResult,
        variables={
            "topic": context.topic,
            "hook": context.hook,
            "key_concepts": "\n".join(f"  - {concept}" for concept in context.key_concepts),
        },
        temperature=0.62,
        max_tokens=1800,  # Phase 2A: Realistic limit for thumbnail concepts (~1400 tokens typical)
    )


async def run_title_strategy_agent(
    *,
    context: TitleContext,
) -> TitleStrategyResult:
    """
    Generate scored title candidates.
    
    Optimized: Receives minimal context (400 tokens) instead of full artifacts (4,500 tokens).
    Token reduction: 91%
    """
    return await generate_structured_artifact(
        prompt_name="studio_title_strategy",
        model=TitleStrategyResult,
        variables={
            "topic": context.topic,
            "hook": context.hook,
            "theme": context.theme,
            "key_facts": "\n".join(f"  - {fact}" for fact in context.key_facts),
        },
        temperature=0.58,
        max_tokens=2000,
    )


async def run_youtube_seo_agent(
    *,
    context: SEOContext,
) -> SEOResult:
    """
    Generate YouTube SEO metadata.
    
    Optimized: Receives minimal context (600 tokens) instead of full artifacts (2,000 tokens).
    Token reduction: 70%
    """
    return await run_seo_agent(
        research=None,  # No longer needed - context has everything
        topic=context.topic,
        tone=context.tone,
        narration_excerpt=context.narration_excerpt,
        keywords=context.keywords,
        key_facts=context.key_facts,
    )


async def run_final_qa_agent(
    *,
    research: ResearchResult,
    script_qa: ScriptQAResult,
    visual_plan: VisualPlanResult,
    asset_collection: AssetCollectionResult,
    audio_qa: AudioQAResult | None,
    editing_plan: EditingPlanResult,
    thumbnails: ThumbnailStrategyResult,
    titles: TitleStrategyResult,
    seo: SEOResult,
) -> FinalQAResult:
    """Run the release-quality gate over all stage artifacts."""
    return await generate_structured_artifact(
        prompt_name="studio_final_qa",
        model=FinalQAResult,
        variables={
            "research_context": research_brief_context(research, rich=True),
            "script_context": script_context(script_qa),
            "visual_plan_context": visual_plan_context(visual_plan),
            "asset_collection_json": asset_collection.model_dump_json(indent=2),
            "audio_qa_json": audio_qa.model_dump_json(indent=2) if audio_qa else "{}",
            "editing_plan_json": editing_plan.model_dump_json(indent=2),
            "thumbnail_json": thumbnails.model_dump_json(indent=2),
            "title_json": titles.model_dump_json(indent=2),
            "seo_json": seo.model_dump_json(indent=2),
        },
        temperature=0.2,
        max_tokens=2600,  # Phase 2A: Realistic limit for QA report (~2000 tokens typical)
    )
