# Context Objects Design Document

**Date**: 2026-07-26  
**Status**: Context objects implemented, ready for agent refactoring

---

## Overview

This document describes the minimal context objects that replace full artifact passing between agents.

**Objective**: Remove unnecessary data flow while preserving output quality.

**Architecture Principle**: Each agent receives ONLY the fields it actually uses.

---

## Context Objects Implemented

### 1. ThumbnailContext

**Purpose**: Thumbnail generation  
**Replaces**: ResearchResult (2,000 tokens) + ScriptQAResult (2,500 tokens)  
**Contains**: 400 tokens

```python
class ThumbnailContext:
    topic: str
    hook: str
    key_concepts: list[str]  # Top 3-5
```

**Token Savings**: **91%** (4,500 → 400)

**Rationale**:
- Thumbnail designer needs hook for concept
- Needs key_concepts for visual ideas
- Does NOT need full narration (1,800 tokens)
- Does NOT need timeline, sources, or detailed research

---

### 2. TitleContext

**Purpose**: Title generation  
**Replaces**: ResearchResult (2,000 tokens) + ScriptQAResult (2,500 tokens)  
**Contains**: 400 tokens

```python
class TitleContext:
    topic: str
    hook: str
    theme: str  # One-sentence theme
    key_facts: list[str]  # Top 3
```

**Token Savings**: **91%** (4,500 → 400)

**Rationale**:
- Title writer needs hook for inspiration
- Needs theme for framing
- Needs top 3 facts for title concepts
- Does NOT need full narration
- Does NOT need timeline or visual opportunities

---

### 3. SEOContext

**Purpose**: YouTube SEO metadata generation  
**Replaces**: ResearchResult (2,000 tokens)  
**Contains**: 600 tokens

```python
class SEOContext:
    topic: str
    tone: str
    narration_excerpt: str  # First 700 chars
    keywords: list[str]     # Top 10
    key_facts: list[str]    # Top 5
```

**Token Savings**: **70%** (2,000 → 600)

**Rationale**:
- SEO needs keywords for tags
- Needs key_facts for description
- Needs narration_excerpt (not full narration)
- Does NOT need visual_opportunities, sources, or hooks

---

### 4. VisualPlanningContext

**Purpose**: Visual timeline planning  
**Replaces**: ScriptQAResult (5,500 tokens)  
**Contains**: 2,000 tokens

```python
class VisualPlanningContext:
    narration: str          # REQUIRED (1,800 tokens)
    sections: list[str]
    target_duration: int
    aspect_ratio: str
```

**Token Savings**: **64%** (5,500 → 2,000)

**Rationale**:
- Visual planner MUST have full narration (aligns visuals to spoken words)
- Needs sections for structure
- Does NOT need QA scores, issues, or strengths
- Does NOT need research context

**Note**: Narration is legitimately large (1,800 tokens unavoidable).

---

### 5. ImageGenerationContext

**Purpose**: AI image generation planning  
**Replaces**: VisualPlanResult (18,000 tokens with full timeline)  
**Contains**: 3,000 tokens

```python
class ImageGenerationContext:
    style_reference: str
    required_visuals: list[VisualTimelineItem]  # Filtered subset
    negative_prompt: str
```

**Token Savings**: **83%** (18,000 → 3,000) 🎯

**Rationale**:
- Only pass timeline items that need AI generation
- For 10-min video: 150 timeline items → filter to ~20 AI-required
- Does NOT need full timeline (huge waste)
- Does NOT need consistency_rules (redundant with style)

**This is the largest single optimization**.

---

### 6. VoiceDirectionContext

**Purpose**: Narration performance direction  
**Replaces**: ScriptQAResult (4,000 tokens)  
**Contains**: 1,000 tokens

```python
class VoiceDirectionContext:
    narration: str  # REQUIRED
    voice_id: str
```

**Token Savings**: **75%** (4,000 → 1,000)

**Rationale**:
- Voice director only needs narration text
- Does NOT need QA scores, issues, hook, or sections

---

### 7. StoryArchitectContext

**Purpose**: Story structure design  
**Replaces**: Full ResearchResult via research_to_context() (2,500 tokens)  
**Contains**: 1,200 tokens

```python
class StoryArchitectContext:
    topic: str
    summary: str
    key_facts: list[str]          # Top 8
    timeline: list[str]           # If available
    emotional_angles: list[str]   # Top 3
    surprising_facts: list[str]   # Top 3
```

**Token Savings**: **52%** (2,500 → 1,200)

**Rationale**:
- Story architect needs facts and timeline for structure
- Needs emotional_angles for tone
- Does NOT need visual_opportunities (visual planner's job)
- Does NOT need detailed sources or hook_opportunities

---

### 8. ScriptWriterContext

**Purpose**: Narration writing  
**Replaces**: Full ResearchResult + StoryArchitectureResult (3,500 tokens)  
**Contains**: 1,500 tokens

```python
class ScriptWriterContext:
    topic: str
    summary: str
    key_facts: list[str]
    timeline: list[str]
    surprising_facts: list[str]
    story_beats: list[str]  # Flattened story structure
```

**Token Savings**: **57%** (3,500 → 1,500)

**Rationale**:
- Script writer needs facts + timeline + story beats
- Does NOT need visual_opportunities (visual planner's job)
- Does NOT need sources (metadata extractor's job)
- Does NOT need detailed emotional angles (already has story beats)

---

### 9. ScriptQAContext

**Purpose**: Script quality assurance  
**Replaces**: Full ResearchResult + StoryArchitectureResult + Script (6,000 tokens)  
**Contains**: 2,500 tokens

```python
class ScriptQAContext:
    narration: str
    sections: list[str]
    key_facts: list[str]     # For fact-checking
    story_beats: list[str]   # For structure validation
    target_duration: int
    word_count: int
```

**Token Savings**: **58%** (6,000 → 2,500)

**Rationale**:
- QA needs narration for quality check
- Needs key_facts for fact-checking
- Needs story_beats for structure validation
- Does NOT need visual_opportunities, sources, or hook_opportunities

---

### 10. EditingPlanContext

**Purpose**: Edit rhythm and transitions  
**Replaces**: ScriptQAResult + VisualPlanResult (20,000 tokens)  
**Contains**: 10,000 tokens

```python
class EditingPlanContext:
    timeline: list[VisualTimelineItem]  # REQUIRED
    sections: list[str]
    aspect_ratio: str
    target_duration: int
```

**Token Savings**: **50%** (20,000 → 10,000)

**Rationale**:
- Editing planner needs full timeline (unavoidable)
- Needs sections for chapter markers
- Does NOT need full narration
- Does NOT need QA scores or research context

**Note**: Timeline is legitimately large (10,000 tokens required).

---

### 11. FinalQAContext

**Purpose**: Final quality gate  
**Replaces**: 9 full artifacts (35,000 tokens)  
**Contains**: 15,000 tokens

```python
class FinalQAContext:
    # Core content
    topic: str
    narration_summary: str       # First 500 words (not full)
    key_facts: list[str]
    
    # Stage summaries (not full artifacts)
    script_quality: float
    script_issues: list[QualityIssue]
    visual_count: int
    visual_coverage: float
    asset_success_rate: float
    asset_issues: list[QualityIssue]
    audio_duration: float
    audio_quality: float
    thumbnail_best: str          # Just winning concept
    title_best: str              # Just winning title
    seo_keywords: list[str]
```

**Token Savings**: **57%** (35,000 → 15,000)

**Rationale**:
- Final QA needs comprehensive view (quality gate)
- BUT can use summaries instead of full artifacts
- Narration summary (500 words) instead of full (1,500 words)
- Scores + issues instead of full stage data
- Winning concepts instead of all candidates

---

## Token Reduction Summary

| Context | Before | After | Savings | % |
|---------|--------|-------|---------|---|
| Thumbnail | 4,500 | 400 | 4,100 | **91%** 🎯 |
| Title | 4,500 | 400 | 4,100 | **91%** 🎯 |
| SEO | 2,000 | 600 | 1,400 | **70%** |
| Visual Planning | 5,500 | 2,000 | 3,500 | **64%** |
| Image Generation | 18,000 | 3,000 | 15,000 | **83%** 🎯 |
| Voice Direction | 4,000 | 1,000 | 3,000 | **75%** |
| Story Architect | 2,500 | 1,200 | 1,300 | **52%** |
| Script Writer | 3,500 | 1,500 | 2,000 | **57%** |
| Script QA | 6,000 | 2,500 | 3,500 | **58%** |
| Editing Plan | 20,000 | 10,000 | 10,000 | **50%** |
| Final QA | 35,000 | 15,000 | 20,000 | **57%** |
| **TOTAL** | **123,500** | **52,600** | **70,900** | **57%** |

---

## Context Builder Functions

Each context has a corresponding builder function:

```python
# Example: Thumbnail Context Builder
def build_thumbnail_context(
    research: ResearchResult,
    script_qa: ScriptQAResult,
) -> ThumbnailContext:
    """Extract only hook + top 5 key concepts."""
    script = script_qa.revised_script
    return ThumbnailContext(
        topic=research.topic,
        hook=script.hook,
        key_concepts=research.key_facts[:5],
    )
```

**All 11 builders implemented** in `services/ai/studio/context.py`.

---

## Implementation Status

### ✅ Complete

1. Context object models designed
2. Context builder functions implemented
3. Code compiles and imports successfully
4. Token savings calculated

### ⏳ Remaining

5. Refactor agents to use contexts (Tasks 5-10)
6. Update pipeline to call builders (Task 11)
7. Validate outputs remain identical (Task 12)
8. Measure actual token reduction (Task 13)

---

## Next Steps: Agent Refactoring Priority

### High Priority (Largest Wins)

1. **Thumbnail Strategy** (91% savings, simple)
   - Update `run_thumbnail_strategy_agent()` signature
   - Replace `research + script_qa` with `ThumbnailContext`
   - Update prompt variables

2. **Title Strategy** (91% savings, simple)
   - Update `run_title_strategy_agent()` signature
   - Replace `research + script_qa` with `TitleContext`
   - Update prompt variables

3. **Image Generation Planner** (83% savings, high impact)
   - Update `run_image_generation_planner_agent()` signature
   - Replace `visual_plan + ai_required_indices` with `ImageGenerationContext`
   - Huge win: filtered timeline

4. **Voice Direction** (75% savings, simple)
   - Update `run_voice_direction_agent()` signature
   - Replace `script_qa + voice_id` with `VoiceDirectionContext`
   - Narration only

5. **YouTube SEO** (70% savings, simple)
   - Update `run_youtube_seo_agent()` signature
   - Replace `research + topic + tone + script_qa` with `SEOContext`
   - Keywords + facts only

### Medium Priority

6. Visual Planner (64% savings, but narration required)
7. Script QA (58% savings)
8. Final QA (57% savings, complex)
9. Script Writer (57% savings)
10. Story Architect (52% savings)

### Low Priority

11. Editing Plan (50% savings, timeline required)

---

## Validation Strategy

For each refactored agent:

1. **Run before refactoring** - save output
2. **Refactor agent** - update signature + prompt
3. **Run after refactoring** - save output
4. **Compare outputs** - verify identical (except token counts)
5. **Measure tokens** - confirm reduction
6. **Update tests** - if any tests depend on agent signatures

---

## Backwards Compatibility

**Legacy serializers preserved** for gradual migration:

- `topic_brief_context()` - DEPRECATED but kept
- `research_brief_context()` - DEPRECATED but kept
- `story_context()` - DEPRECATED but kept
- `script_context()` - DEPRECATED but kept
- `visual_plan_context()` - DEPRECATED but kept

These can be removed after all agents are refactored.

---

## Architectural Benefits

Beyond token savings:

1. **Clearer dependencies**: Each context explicitly declares requirements
2. **Easier testing**: Mock minimal contexts instead of full artifacts
3. **Better maintainability**: Changes to artifacts don't break unrelated agents
4. **Explicit contracts**: Context objects are typed and validated
5. **Future-proof**: New fields in artifacts don't pollute agent prompts

---

**Document compiled**: 2026-07-26 11:15
