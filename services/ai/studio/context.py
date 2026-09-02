"""
Minimal context objects for agent communication.

This module defines context objects that replace full artifact passing.
Each context contains ONLY the fields required by its target agent.

Architecture principle:
  Agents receive minimal context objects, not full artifacts.
  Context builders extract only required fields from artifacts.

Token optimization:
  Before: Agents received 2,500-35,000 token artifacts
  After: Agents receive 400-15,000 token minimal contexts
  Savings: 57% reduction in downstream token usage
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
import re as _re
from services.ai.research import research_to_context, research_to_summary
from services.ai.schemas import (
    AssetCollectionResult,
    AudioQAResult,
    DocumentaryMetadata,
    DocumentaryNarration,
    DocumentaryScriptResult,
    EditingPlanResult,
    QualityIssue,
    ResearchResult,
    ScriptQAResult,
    SEOResult,
    StoryArchitectureResult,
    ThumbnailStrategyResult,
    TitleStrategyResult,
    TopicIntelligenceResult,
    VisualPlanResult,
    VisualTimelineItem,
)


# ── Minimal Context Objects ───────────────────────────────────────────────────

class ThumbnailContext(BaseModel):
    """
    Minimal context for thumbnail generation.
    
    Replaces: ResearchResult (2,000 tokens) + ScriptQAResult (2,500 tokens)
    Contains: Only hook + key concepts (~400 tokens)
    Savings: 91%
    """
    model_config = ConfigDict(extra="allow")
    
    topic: str
    hook: str
    key_concepts: list[str] = Field(default_factory=list, description="Top 3-5 key facts/concepts")


class TitleContext(BaseModel):
    """
    Minimal context for title generation.
    
    Replaces: ResearchResult (2,000 tokens) + ScriptQAResult (2,500 tokens)
    Contains: Only hook + theme + key facts (~400 tokens)
    Savings: 91%
    """
    model_config = ConfigDict(extra="allow")
    
    topic: str
    hook: str
    theme: str = Field(..., description="One-sentence theme from script")
    key_facts: list[str] = Field(default_factory=list, description="Top 3-5 facts")


class SEOContext(BaseModel):
    """
    Minimal context for SEO generation.
    
    Replaces: ResearchResult (2,000 tokens)
    Contains: Keywords + facts + excerpt (~600 tokens)
    Savings: 70%
    """
    model_config = ConfigDict(extra="allow")
    
    topic: str
    tone: str
    narration_excerpt: str = Field(..., description="First 700 characters of narration")
    keywords: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list, description="Top 5 facts")


class VisualPlanningContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    narration: str = Field(..., description="Complete narration for visual alignment")
    sections: list[str] = Field(default_factory=list)
    section_timings: list[dict] = Field(
        default_factory=list,
        description="Real per-section start/end seconds and word counts, when available",
    )
    target_duration: int
    aspect_ratio: str



class ImageGenerationContext(BaseModel):
    """
    Minimal context for AI image generation planning.
    
    Replaces: Full VisualPlanResult (18,000 tokens with complete timeline)
    Contains: Style + required visuals only (~3,000 tokens)
    Savings: 83%
    """
    model_config = ConfigDict(extra="allow")
    
    style_reference: str
    required_visuals: list[VisualTimelineItem] = Field(default_factory=list, description="Only AI-required items")
    negative_prompt: str = "distorted faces, unreadable text, extra fingers, artifacts, watermark, logo errors"


class VoiceDirectionContext(BaseModel):
    """
    Minimal context for voice direction.
    
    Replaces: ScriptQAResult (4,000 tokens)
    Contains: Narration only (~1,000 tokens)
    Savings: 75%
    """
    model_config = ConfigDict(extra="allow")
    
    narration: str = Field(..., description="Complete narration for performance direction")
    voice_id: str


class StoryArchitectContext(BaseModel):
    """
    Minimal context for story architecture.
    
    Replaces: Full ResearchResult via research_to_context() (2,500 tokens)
    Contains: Summary + core facts (~1,000 tokens)
    Savings: 60%
    
    Phase 2B: Removed timeline field (200 tokens) - story structure uses emotional beats, not chronology
    """
    model_config = ConfigDict(extra="allow")
    
    topic: str
    summary: str
    key_facts: list[str] = Field(default_factory=list, description="Top 8 facts")
    emotional_angles: list[str] = Field(default_factory=list, description="Top 3 angles")
    surprising_facts: list[str] = Field(default_factory=list, description="Top 3 facts")


class ScriptWriterContext(BaseModel):
    """
    Minimal context for script/narration writing.
    
    Replaces: Full ResearchResult (3,500 tokens)
    Contains: Summary + facts + story beats (~1,200 tokens)
    Savings: 66%
    
    Phase 2B: Removed timeline field (300 tokens) - chronology is embedded in story_beats
    """
    model_config = ConfigDict(extra="allow")
    
    topic: str
    summary: str
    key_facts: list[str] = Field(default_factory=list)
    surprising_facts: list[str] = Field(default_factory=list)
    story_beats: list[str] = Field(default_factory=list, description="Flattened story structure with chronology")


class ScriptQAContext(BaseModel):
    """
    Minimal context for script quality assurance.
    
    Replaces: Full ResearchResult + StoryArchitectureResult (6,000 tokens)
    Contains: Narration + validation data (~2,500 tokens)
    Savings: 58%
    """
    model_config = ConfigDict(extra="allow")
    
    narration: str
    sections: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list, description="For fact-checking")
    story_beats: list[str] = Field(default_factory=list, description="For structure validation")
    target_duration: int
    word_count: int


class EditingPlanContext(BaseModel):
    """
    Minimal context for editing plan generation.
    
    Replaces: Full ScriptQAResult + VisualPlanResult (20,000 tokens)
    Contains: Timeline + sections (~10,000 tokens)
    Savings: 50%
    
    Note: Timeline is required (large but necessary).
    """
    model_config = ConfigDict(extra="allow")
    
    timeline: list[VisualTimelineItem] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    aspect_ratio: str
    target_duration: int


class FinalQAContext(BaseModel):
    """
    Minimal context for final quality gate.
    
    Replaces: 9 full artifacts (35,000 tokens)
    Contains: Summaries + scores + issues (~15,000 tokens)
    Savings: 57%
    """
    model_config = ConfigDict(extra="allow")
    
    # Core content
    topic: str
    narration_summary: str = Field(..., description="First 500 words of narration")
    key_facts: list[str] = Field(default_factory=list)
    
    # Stage summaries
    script_quality: float
    script_issues: list[QualityIssue] = Field(default_factory=list)
    
    visual_count: int
    visual_coverage: float = Field(..., description="Percentage of video covered by visuals")
    
    asset_success_rate: float = Field(..., description="Percentage of assets successfully collected")
    asset_issues: list[QualityIssue] = Field(default_factory=list)
    
    audio_duration: float
    audio_quality: float
    
    thumbnail_best: str = Field(..., description="Winning thumbnail concept")
    title_best: str = Field(..., description="Winning title")
    seo_keywords: list[str] = Field(default_factory=list)


# ── Legacy Context Serializers (deprecated, keep for backwards compat) ────────


def topic_brief_context(brief: TopicIntelligenceResult) -> str:
    """DEPRECATED: Use context objects instead."""
    return "\n".join(
        [
            f"TOPIC: {brief.topic}",
            f"AUDIENCE: {brief.target_audience}",
            f"SEARCH INTENT: {brief.search_intent}",
            f"DEPTH: {brief.educational_depth}",
            f"EMOTIONAL ANGLE: {brief.emotional_angle}",
            f"LENGTH: {brief.recommended_video_length_seconds}s",
            f"STYLE: {brief.recommended_storytelling_style}",
            "VIEWER EXPECTATIONS:",
            *[f"  - {item}" for item in brief.viewer_expectations[:8]],
        ]
    )


def research_brief_context(research: ResearchResult, rich: bool = False) -> str:
    """DEPRECATED: Use context objects instead."""
    return research_to_context(research) if rich else research_to_summary(research)


def story_context(story: StoryArchitectureResult) -> str:
    """DEPRECATED: Use context objects instead."""
    return "\n".join(
        [
            f"OPENING HOOK: {story.opening_hook}",
            f"CENTRAL CONFLICT: {story.central_conflict}",
            "TURNING POINTS:",
            *[f"  - {item}" for item in story.key_turning_points],
            f"CLIMAX: {story.climax}",
            f"CONCLUSION: {story.conclusion}",
            "EMOTIONAL PROGRESSION:",
            *[f"  - {item}" for item in story.emotional_progression],
        ]
    )


def script_context(script: DocumentaryScriptResult | ScriptQAResult) -> str:
    """DEPRECATED: Use context objects instead."""
    if isinstance(script, ScriptQAResult):
        script = script.revised_script
    sections = "\n".join(f"  - {section}" for section in script.sections[:12])
    return (
        f"HOOK: {script.hook}\n"
        f"ESTIMATED DURATION: {script.estimated_duration_seconds}s\n"
        f"SECTIONS:\n{sections}\n\n"
        f"NARRATION:\n{script.narration}"
    )


def visual_plan_context(plan: VisualPlanResult, max_beats: int = 20) -> str:
    """
    Compact timeline summary for prompts needing transition/pacing context,
    not full per-beat text. Previously unbounded — at high beat counts (a
    240s+ video with many chapters easily produces 40-50+ beats) this
    serialized the ENTIRE timeline verbatim, which is what produced a
    42,000-token single call and starved the rest of the run's quota.
    """
    lines = [f"VISUAL STYLE: {plan.visual_style}", f"TIMELINE ({len(plan.timeline)} beats total):"]
    for item in plan.timeline[:max_beats]:
        on_screen = item.on_screen[:80] + ("…" if len(item.on_screen) > 80 else "")
        lines.append(
            f"  {item.index}. {item.start_seconds:.1f}-{item.end_seconds:.1f}s "
            f"[{item.asset_type.value}] {on_screen}"
        )
    if len(plan.timeline) > max_beats:
        lines.append(f"  ... and {len(plan.timeline) - max_beats} more beats (omitted for brevity)")
    return "\n".join(lines)


# ── Context Builder Functions ─────────────────────────────────────────────────


def build_thumbnail_context(
    research: ResearchResult,
    script_qa: ScriptQAResult,
) -> ThumbnailContext:
    """
    Build minimal context for thumbnail generation.
    
    Extracts: topic, hook, top 5 key concepts
    Token reduction: 4,500 → 400 tokens (91%)
    """
    script = script_qa.revised_script
    
    # Extract top 5 key concepts from research facts
    key_concepts = research.key_facts[:5]
    
    return ThumbnailContext(
        topic=research.topic,
        hook=script.hook,
        key_concepts=key_concepts,
    )


def build_title_context(
    research: ResearchResult,
    script_qa: ScriptQAResult,
) -> TitleContext:
    """
    Build minimal context for title generation.
    
    Extracts: topic, hook, theme, top 3 facts
    Token reduction: 4,500 → 400 tokens (91%)
    """
    script = script_qa.revised_script
    
    # Extract theme (one-sentence summary from executive summary)
    theme = research.executive_summary.split('.')[0] + '.'
    
    return TitleContext(
        topic=research.topic,
        hook=script.hook,
        theme=theme,
        key_facts=research.key_facts[:3],
    )


def build_seo_context(
    research: ResearchResult,
    topic: str,
    tone: str,
    script_qa: ScriptQAResult,
) -> SEOContext:
    """
    Build minimal context for SEO generation.
    
    Extracts: topic, tone, narration excerpt, keywords, top 5 facts
    Token reduction: 2,000 → 600 tokens (70%)
    """
    script = script_qa.revised_script
    
    return SEOContext(
        topic=topic,
        tone=tone,
        narration_excerpt=script.narration[:700],
        keywords=research.search_keywords[:10],
        key_facts=research.key_facts[:5],
    )


def _split_sentences(text: str) -> list[str]:
    return [s for s in _re.split(r'(?<=[.!?])\s+', text.strip()) if s]

def _build_sentence_timings(full_narration: str, section_metadata: list) -> list[dict]:
    words = full_narration.split()
    cursor = 0
    timings: list[dict] = []
    for section in section_metadata:
        n = section.actual_word_count
        section_text = " ".join(words[cursor:cursor + n])
        cursor += n
        sentences = _split_sentences(section_text)
        wcs = [max(1, len(s.split())) for s in sentences]
        total = sum(wcs) or 1
        t = section.start_time_seconds
        for sentence, wc in zip(sentences, wcs):
            share = section.duration_seconds * (wc / total)
            timings.append({"text": sentence, "start_seconds": round(t, 2), "end_seconds": round(t + share, 2)})
            t += share
    return timings

def build_visual_planning_context(
    script_qa: ScriptQAResult,
    target_duration: int,
    aspect_ratio: str,
) -> VisualPlanningContext:
    script = script_qa.revised_script

    section_timings = []
    if script.section_metadata:
        for s in script.section_metadata:
            section_timings.append({
                "title": s.title,
                "start_seconds": s.start_time_seconds,
                "end_seconds": round(s.start_time_seconds + s.duration_seconds, 2),
                "word_count": s.actual_word_count,
            })

    sentence_timings = _build_sentence_timings(script.narration, script.section_metadata) if script.section_metadata else []
    
    return VisualPlanningContext(
        narration=script.narration, 
        sections=script.sections,
        section_timings=section_timings, 
        sentence_timings=sentence_timings,
        target_duration=target_duration, 
        aspect_ratio=aspect_ratio
    )

    

def build_image_generation_context(
    visual_plan: VisualPlanResult,
    ai_required_indices: list[int],
) -> ImageGenerationContext:
    """
    Build minimal context for AI image generation.
    
    Extracts: style + only the timeline items that need AI generation
    Token reduction: 18,000 → 3,000 tokens (83%)
    
    Huge win: Filters timeline to only required items instead of passing everything.
    """
    # Filter timeline to only AI-required items
    required_visuals = [
        item for item in visual_plan.timeline
        if item.index in ai_required_indices
    ]
    
    return ImageGenerationContext(
        style_reference=visual_plan.visual_style,
        required_visuals=required_visuals,
        negative_prompt="distorted faces, unreadable text, extra fingers, artifacts, watermark, logo errors",
    )


def build_voice_direction_context(
    script_qa: ScriptQAResult,
    voice_id: str,
) -> VoiceDirectionContext:
    """
    Build minimal context for voice direction.
    
    Extracts: narration only
    Token reduction: 4,000 → 1,000 tokens (75%)
    """
    script = script_qa.revised_script
    
    return VoiceDirectionContext(
        narration=script.narration,
        voice_id=voice_id,
    )


def build_story_architect_context(
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    target_duration: int,
) -> StoryArchitectContext:
    """
    Build minimal context for story architecture.
    
    Extracts: summary + core facts (no timeline, visuals, sources, or detailed angles)
    Token reduction: 2,500 → 1,000 tokens (60%)
    
    Phase 2B: Removed timeline - story structure focuses on emotional beats, not chronology
    """
    # Extract top emotional angles (just the angle names, not full descriptions)
    emotional_angles = [
        ea.angle if hasattr(ea, 'angle') else str(ea)
        for ea in research.emotional_angles[:3]
    ]
    
    return StoryArchitectContext(
        topic=research.topic,
        summary=research.executive_summary,
        key_facts=research.key_facts[:8],
        emotional_angles=emotional_angles,
        surprising_facts=research.surprising_facts[:3],
    )


def build_script_writer_context(
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
) -> ScriptWriterContext:
    """
    Build minimal context for script/narration writing.
    
    Extracts: summary + facts + flattened story beats
    Token reduction: 3,500 → 1,200 tokens (66%)
    
    Phase 2B: Removed timeline - chronology is embedded in story_beats already
    """
    # Flatten story structure into simple beats (includes chronology)
    story_beats = [
        f"Opening: {story.opening_hook}",
        f"Conflict: {story.central_conflict}",
        *[f"Beat: {tp}" for tp in story.key_turning_points],
        f"Climax: {story.climax}",
        f"Conclusion: {story.conclusion}",
    ]
    
    return ScriptWriterContext(
        topic=research.topic,
        summary=research.executive_summary,
        key_facts=research.key_facts,
        surprising_facts=research.surprising_facts,
        story_beats=story_beats,
    )


def build_script_qa_context(
    script: DocumentaryScriptResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int,
) -> ScriptQAContext:
    """
    Build minimal context for script QA.
    
    Extracts: narration + validation criteria
    Token reduction: 6,000 → 2,500 tokens (58%)
    """
    # Flatten story for validation
    story_beats = [
        story.opening_hook,
        story.central_conflict,
        *story.key_turning_points,
        story.climax,
        story.conclusion,
    ]
    
    return ScriptQAContext(
        narration=script.narration,
        sections=script.sections,
        key_facts=research.key_facts,
        story_beats=story_beats,
        target_duration=target_duration,
        word_count=len(script.narration.split()),
    )


def build_editing_plan_context(
    script_qa: ScriptQAResult,
    visual_plan: VisualPlanResult,
    aspect_ratio: str,
    target_duration: int,
) -> EditingPlanContext:
    """
    Build minimal context for editing plan.
    
    Extracts: timeline + sections (no full narration)
    Token reduction: 20,000 → 10,000 tokens (50%)
    
    Note: Timeline is large but required.
    """
    script = script_qa.revised_script
    
    return EditingPlanContext(
        timeline=visual_plan.timeline,
        sections=script.sections,
        aspect_ratio=aspect_ratio,
        target_duration=target_duration,
    )


def build_final_qa_context(
    research: ResearchResult,
    script_qa: ScriptQAResult,
    visual_plan: VisualPlanResult,
    asset_collection: AssetCollectionResult,
    audio_qa: AudioQAResult | None,
    editing_plan: EditingPlanResult,
    thumbnails: ThumbnailStrategyResult,
    titles: TitleStrategyResult,
    seo: SEOResult,
) -> FinalQAContext:
    """
    Build minimal context for final QA.
    
    Extracts: Summaries + scores instead of full artifacts
    Token reduction: 35,000 → 15,000 tokens (57%)
    """
    script = script_qa.revised_script
    
    # Narration summary (first 500 words)
    narration_words = script.narration.split()
    narration_summary = ' '.join(narration_words[:500])
    if len(narration_words) > 500:
        narration_summary += '...'
    
    # Calculate visual coverage
    total_duration = max(item.end_seconds for item in visual_plan.timeline) if visual_plan.timeline else 0
    visual_coverage = (total_duration / script.estimated_duration_seconds * 100) if script.estimated_duration_seconds > 0 else 0
    
    # Calculate asset success rate
    total_assets = len(asset_collection.selected_assets) + len(asset_collection.ai_required_indices)
    successful_assets = len(asset_collection.selected_assets)
    asset_success_rate = (successful_assets / total_assets * 100) if total_assets > 0 else 0
    
    return FinalQAContext(
        topic=research.topic,
        narration_summary=narration_summary,
        key_facts=research.key_facts[:5],
        script_quality=script_qa.score,
        script_issues=script_qa.issues,
        visual_count=len(visual_plan.timeline),
        visual_coverage=visual_coverage,
        asset_success_rate=asset_success_rate,
        asset_issues=asset_collection.issues,
        audio_duration=audio_qa.duration_seconds if audio_qa else 0,
        audio_quality=audio_qa.score if audio_qa else 0,
        thumbnail_best=thumbnails.concepts[thumbnails.best_index].concept if thumbnails.concepts else "",
        title_best=titles.candidates[titles.best_index].title if titles.candidates else "",
        seo_keywords=seo.tags[:10],
    )
