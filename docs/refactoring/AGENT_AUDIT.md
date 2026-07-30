# Agent Dependency Audit

**Date**: 2026-07-26  
**Objective**: Document what each agent receives vs. what it actually uses

---

## Audit Summary

| Agent | Current Inputs | Fields Actually Used | Unused Data | Est. Prompt Tokens | Min Required Tokens | Waste |
|-------|----------------|---------------------|-------------|-------------------|---------------------|-------|
| Topic Intelligence | topic, audience, goal | ALL | None | ~800 | ~800 | 0% |
| Research | topic, tone, duration, platform | ALL | None | ~1,200 | ~1,200 | 0% |
| Story Architect | brief, research | topic, summary, facts, hooks, timeline | visual_opportunities, detailed_angles, sources | ~2,500 | ~1,200 | **52%** |
| Script Writer | brief, research, story | topic, summary, facts, story | visual_opportunities, sources, misconceptions | ~3,500 | ~1,500 | **57%** |
| Script QA | script, research, story | script.narration, script.sections, story, research.facts | research.visuals, research.hooks, story.pacing | ~6,000 | ~2,500 | **58%** |
| Visual Planner | script_qa, duration, aspect_ratio | narration, sections, duration | research, story, qa.issues, qa.strengths | ~5,500 | ~1,000 | **82%** |
| Asset Collection | visual_plan | timeline only | style, consistency_rules | ~18,000 | ~15,000 | 17% |
| Image Gen Planner | visual_plan, ai_required_indices | visual_plan.timeline[indices], style | full timeline, consistency | ~18,000 | ~8,000 | **56%** |
| Voice Direction | script_qa, voice_id | narration only | script, qa data, research | ~4,000 | ~1,000 | **75%** |
| Audio QA | audio_path, duration | file analysis | (non-LLM) | N/A | N/A | N/A |
| Editing Plan | script_qa, visual_plan, aspect_ratio | sections, timeline | narration, research, full script | ~20,000 | ~10,000 | **50%** |
| Thumbnail Strategy | research, script_qa | hook, key_facts, topic | full narration, timeline, sources | ~4,500 | ~400 | **91%** |
| Title Strategy | research, script_qa | hook, topic, key_facts | full narration, timeline, sources | ~4,500 | ~400 | **91%** |
| YouTube SEO | research, topic, tone, script_qa | hook, facts, keywords, narration[0:700] | full script, timeline, sources | ~2,000 | ~600 | **70%** |
| Final QA | research, script_qa, visual_plan, asset_collection, audio_qa, editing_plan, thumbnails, titles, seo | Everything (quality gate) | None (needs full context) | ~35,000 | ~15,000 | **57%** |

**Total Pipeline Waste**: ~**70,000 tokens** per video (45% of 154,600)

---

## Detailed Agent Analysis

### 1. Topic Intelligence Agent

**File**: `services/ai/studio/topic_intelligence.py`

**Receives**:
- `topic: str`
- `audience_profile: str`
- `monetization_goal: str`

**Uses**: ALL (correctly scoped)

**Produces**: `TopicIntelligenceResult`

**Est. Prompt Tokens**: ~800

**Optimization**: ✅ None needed (already minimal)

---

### 2. Research Agent

**File**: `services/ai/research.py`

**Receives**:
- `topic: str`
- `tone: str`
- `duration: int`
- `platform: str`
- `audience_profile: str`

**Uses**: ALL (correctly scoped)

**Produces**: `ResearchResult`

**Est. Prompt Tokens**: ~1,200

**Optimization**: ✅ None needed (already minimal)

---

### 3. Story Architect Agent

**File**: `services/ai/studio/story_architect.py`

**Receives**:
- `brief: TopicIntelligenceResult` (full object)
- `research: ResearchResult` (full object via `research_to_context()`)
- `target_duration: int`

**Prompt Variables**:
```python
{
    "topic_brief": topic_brief_context(brief),           # ~200 tokens
    "research_context": research_to_context(research),   # ~1,200 tokens
    "target_duration": target_duration,
}
```

**Actually Uses from Research**:
- ✅ `executive_summary`
- ✅ `key_facts`
- ✅ `timeline`
- ✅ `surprising_facts`
- ✅ `emotional_angles`
- ❌ `visual_opportunities` (not used for story structure)
- ❌ `reliable_sources` (not used)
- ❌ `misconceptions` (included but not central)
- ❌ `interesting_stats` (included but not central)
- ❌ `hook_opportunities` (partial use)

**Optimization**:
```python
class StoryArchitectContext:
    topic: str
    summary: str
    key_facts: list[str]  # Top 8
    timeline: list[str]   # If available
    emotional_angles: list[str]  # Top 3
    surprising_facts: list[str]  # Top 3
```

**Token Reduction**: 2,500 → 1,200 tokens (**52% savings**)

---

### 4. Script Writer Agent (NEW)

**File**: `services/ai/studio/script_writer_v2.py`

**Receives**:
- `brief: TopicIntelligenceResult`
- `research: ResearchResult` (via `research_to_context()`)
- `story: StoryArchitectureResult`
- `target_duration: int`

**Actually Uses**:
- ✅ `topic`
- ✅ `executive_summary`
- ✅ `key_facts`
- ✅ `timeline`
- ✅ `surprising_facts`
- ✅ `story.opening_hook`
- ✅ `story.turning_points`
- ✅ `story.climax`
- ✅ `story.conclusion`
- ❌ `visual_opportunities` (visual planner's job)
- ❌ `reliable_sources` (metadata extractor's job)
- ❌ `hook_opportunities` (already has story.opening_hook)

**Optimization**:
```python
class ScriptWriterContext:
    topic: str
    summary: str
    key_facts: list[str]
    timeline: list[str]
    surprising_facts: list[str]
    story_beats: list[str]  # Flattened from story architecture
```

**Token Reduction**: 3,500 → 1,500 tokens (**57% savings**)

---

### 5. Script QA Agent

**File**: `services/ai/studio/script_qa.py`

**Receives**:
- `script: DocumentaryScriptResult`
- `research: ResearchResult` (via `research_brief_context()` compact)
- `story: StoryArchitectureResult`
- `target_duration: int`

**Actually Uses**:
- ✅ `script.narration` (for quality check)
- ✅ `script.sections` (for structure check)
- ✅ `research.key_facts` (for fact-checking)
- ✅ `story.structure` (for pacing check)
- ❌ `research.visual_opportunities` (not relevant)
- ❌ `research.hook_opportunities` (not relevant)
- ❌ `research.reliable_sources` (not used in QA)
- ❌ `story.emotional_progression` (partial use)

**Optimization**:
```python
class ScriptQAContext:
    narration: str
    sections: list[str]
    key_facts: list[str]  # For fact-checking
    story_beats: list[str]  # For structure validation
    target_duration: int
    word_count: int
```

**Token Reduction**: 6,000 → 2,500 tokens (**58% savings**)

---

### 6. Visual Planning Agent

**File**: `services/ai/studio/visual_planner.py`

**Receives**:
- `script_qa: ScriptQAResult` (includes full script via `script_context()`)
- `target_duration: int`
- `aspect_ratio: str`

**Prompt Uses**:
```python
{
    "narration": script_qa.revised_script.narration,  # ~1,800 tokens
    "sections": script_qa.revised_script.sections,    # ~100 tokens
    "target_duration": target_duration,
    "aspect_ratio": aspect_ratio,
}
```

**Actually Uses**:
- ✅ `narration` (CRITICAL - must align visuals to spoken words)
- ✅ `sections` (for structure)
- ✅ `target_duration`
- ✅ `aspect_ratio`
- ❌ `script_qa.score`
- ❌ `script_qa.issues`
- ❌ `script_qa.strengths`
- ❌ Full `script_context()` includes hook and estimated_duration (redundant)

**Optimization**:
```python
class VisualPlanningContext:
    narration: str  # REQUIRED (can't reduce)
    sections: list[str]
    target_duration: int
    aspect_ratio: str
```

**Token Reduction**: 5,500 → 2,000 tokens (**64% savings**)

**Note**: Narration is legitimately needed (1,800 tokens unavoidable).

---

### 7. Asset Collection Service

**File**: `services/ai/studio/asset_collection.py`

**Receives**:
- `visual_plan: VisualPlanResult` (full object)

**Actually Uses**:
- ✅ `visual_plan.timeline` (all items)
- ❌ `visual_plan.visual_style` (not used by collectors)
- ❌ `visual_plan.consistency_rules` (not used by collectors)

**Optimization**:
```python
class AssetCollectionContext:
    timeline: list[VisualTimelineItem]  # Required
```

**Token Reduction**: 18,000 → 15,000 tokens (**17% savings**)

**Note**: Timeline is legitimately large (10-min video = ~75-150 items).

---

### 8. Image Generation Planner Agent

**File**: `services/ai/studio/visual_planner.py` (`run_image_generation_planner_agent`)

**Receives**:
- `visual_plan: VisualPlanResult`
- `ai_required_indices: list[int]`

**Actually Uses**:
- ✅ `visual_plan.visual_style`
- ✅ `visual_plan.timeline[i]` where `i in ai_required_indices`
- ❌ Full timeline (only needs subset)
- ❌ `consistency_rules` (included but redundant with style)

**Optimization**:
```python
class ImageGenerationContext:
    style_reference: str
    required_visuals: list[VisualTimelineItem]  # Filtered subset only
    negative_prompt: str
```

**Token Reduction**: 18,000 → 3,000 tokens (**83% savings**)

**Note**: Huge win by filtering timeline to only AI-required items.

---

### 9. Voice Direction Agent

**File**: `services/ai/studio/voice_director.py`

**Receives**:
- `script_qa: ScriptQAResult` (via `script_context()`)
- `requested_voice_id: str`

**Actually Uses**:
- ✅ `narration` (for performance direction)
- ❌ `script_qa.score`
- ❌ `script_qa.issues`
- ❌ `script_qa.strengths`
- ❌ `hook`
- ❌ `sections`
- ❌ `estimated_duration`

**Optimization**:
```python
class VoiceDirectionContext:
    narration: str  # REQUIRED
    voice_id: str
```

**Token Reduction**: 4,000 → 1,000 tokens (**75% savings**)

---

### 10. Editing Plan Agent

**File**: `services/ai/studio/editing.py`

**Receives**:
- `script_qa: ScriptQAResult`
- `visual_plan: VisualPlanResult`
- `aspect_ratio: str`

**Actually Uses**:
- ✅ `visual_plan.timeline` (for edit planning)
- ✅ `script_qa.revised_script.sections` (for chapter markers)
- ❌ Full narration (not needed for edit plan)
- ❌ Research context
- ❌ QA scores

**Optimization**:
```python
class EditingPlanContext:
    timeline: list[VisualTimelineItem]
    sections: list[str]
    aspect_ratio: str
    target_duration: int
```

**Token Reduction**: 20,000 → 10,000 tokens (**50% savings**)

---

### 11. Thumbnail Strategy Agent

**File**: `services/ai/studio/packaging.py`

**Receives**:
- `research: ResearchResult` (via `research_brief_context()`)
- `script_qa: ScriptQAResult` (via `script_context()`)

**Prompt includes**:
```python
{
    "research_context": research_brief_context(research),  # ~400 tokens
    "script_context": script_context(script_qa),           # ~2,500 tokens
}
```

**Actually Uses**:
- ✅ `script.hook` (for thumbnail concept)
- ✅ `research.topic` (for context)
- ✅ Top 3 `key_facts` (for visual ideas)
- ❌ Full `narration` (1,800 tokens - NOT needed)
- ❌ `sections` (not used)
- ❌ `timeline` (not used)
- ❌ `visual_opportunities` (not used - thumbnail is different)
- ❌ `hook_opportunities` (not used - already have script.hook)

**Optimization**:
```python
class ThumbnailContext:
    topic: str
    hook: str
    key_concepts: list[str]  # Top 3-5 facts
```

**Token Reduction**: 4,500 → 400 tokens (**91% savings** 🎯)

---

### 12. Title Strategy Agent

**File**: `services/ai/studio/packaging.py`

**Receives**:
- `research: ResearchResult` (via `research_brief_context()`)
- `script_qa: ScriptQAResult` (via `script_context()`)

**Actually Uses**:
- ✅ `script.hook` (for title inspiration)
- ✅ `research.topic` (for context)
- ✅ Top 3 `key_facts` (for title concepts)
- ❌ Full `narration` (NOT needed)
- ❌ `sections` (not used)
- ❌ `timeline` (not used)
- ❌ `hook_opportunities` (not used - already have script.hook)

**Optimization**:
```python
class TitleContext:
    topic: str
    hook: str
    theme: str  # One-sentence theme from script
    key_facts: list[str]  # Top 3
```

**Token Reduction**: 4,500 → 400 tokens (**91% savings** 🎯)

---

### 13. YouTube SEO Agent

**File**: `services/ai/seo.py` (called from `packaging.py`)

**Receives**:
- `research: ResearchResult` (full object)
- `topic: str`
- `tone: str`
- `narration_excerpt: str` (first 700 chars)

**Actually Uses**:
- ✅ `topic`
- ✅ `tone`
- ✅ `narration_excerpt` (for description)
- ✅ `research.search_keywords`
- ✅ `research.key_facts` (for description)
- ❌ Full research object (includes visuals, hooks, sources - NOT needed)

**Optimization**:
```python
class SEOContext:
    topic: str
    tone: str
    narration_excerpt: str  # First 700 chars
    keywords: list[str]
    key_facts: list[str]  # Top 5
```

**Token Reduction**: 2,000 → 600 tokens (**70% savings**)

---

### 14. Final QA Agent

**File**: `services/ai/studio/packaging.py`

**Receives**:
- `research: ResearchResult` (via `research_brief_context(rich=True)`)
- `script_qa: ScriptQAResult` (via `script_context()`)
- `visual_plan: VisualPlanResult` (via `visual_plan_context()`)
- `asset_collection: AssetCollectionResult` (full JSON)
- `audio_qa: AudioQAResult` (full JSON)
- `editing_plan: EditingPlanResult` (full JSON)
- `thumbnails: ThumbnailStrategyResult` (full JSON)
- `titles: TitleStrategyResult` (full JSON)
- `seo: SEOResult` (full JSON)

**Actually Uses**:
- ✅ ALL (this is a quality gate - needs comprehensive context)

**BUT** can be optimized by:
- Using summaries instead of full objects
- Passing only scores + issues, not full data

**Optimization**:
```python
class FinalQAContext:
    # Core content
    topic: str
    narration_summary: str  # First 500 words
    key_facts: list[str]
    
    # Stage summaries
    script_quality: float
    script_issues: list[QualityIssue]
    
    visual_count: int
    visual_coverage: float
    
    asset_success_rate: float
    asset_issues: list[QualityIssue]
    
    audio_duration: float
    audio_quality: float
    
    thumbnail_best: str  # Just the winning concept
    title_best: str      # Just the winning title
    seo_keywords: list[str]
```

**Token Reduction**: 35,000 → 15,000 tokens (**57% savings**)

---

## Token Reduction Summary

| Agent | Before | After | Savings | % |
|-------|--------|-------|---------|---|
| Story Architect | 2,500 | 1,200 | 1,300 | 52% |
| Script Writer | 3,500 | 1,500 | 2,000 | 57% |
| Script QA | 6,000 | 2,500 | 3,500 | 58% |
| Visual Planner | 5,500 | 2,000 | 3,500 | 64% |
| Asset Collection | 18,000 | 15,000 | 3,000 | 17% |
| Image Gen Planner | 18,000 | 3,000 | 15,000 | **83%** |
| Voice Direction | 4,000 | 1,000 | 3,000 | 75% |
| Editing Plan | 20,000 | 10,000 | 10,000 | 50% |
| Thumbnail Strategy | 4,500 | 400 | 4,100 | **91%** |
| Title Strategy | 4,500 | 400 | 4,100 | **91%** |
| YouTube SEO | 2,000 | 600 | 1,400 | 70% |
| Final QA | 35,000 | 15,000 | 20,000 | 57% |
| **TOTAL** | **123,500** | **52,600** | **70,900** | **57%** |

**Aggregate Savings**: **70,900 tokens per video** (57% reduction in downstream context)

---

## Biggest Optimization Wins

1. **Image Generation Planner**: -15,000 tokens (83%) - Filter timeline to AI-required items only
2. **Final QA**: -20,000 tokens (57%) - Use summaries instead of full artifacts
3. **Editing Plan**: -10,000 tokens (50%) - Remove narration, keep timeline + sections
4. **Thumbnail Strategy**: -4,100 tokens (91%) - Remove narration, keep hook + concepts
5. **Title Strategy**: -4,100 tokens (91%) - Remove narration, keep hook + theme

---

## Implementation Priority

### High Priority (Largest Wins)
1. ✅ Thumbnail Strategy (91% savings, simple)
2. ✅ Title Strategy (91% savings, simple)
3. ✅ Image Generation Planner (83% savings, filter timeline)
4. ✅ Voice Direction (75% savings, narration only)
5. ✅ YouTube SEO (70% savings, simple)

### Medium Priority
6. Visual Planner (64% savings, but narration is required)
7. Script QA (58% savings)
8. Final QA (57% savings, complex)
9. Script Writer (57% savings)
10. Story Architect (52% savings)

### Low Priority (Smaller Wins)
11. Editing Plan (50% savings, but timeline required)
12. Asset Collection (17% savings, timeline required)

---

## Next Steps

1. **Design Context Objects** (Step 2)
   - Create Pydantic models for each context type
   - Add to `services/ai/studio/context.py`

2. **Implement Context Builders** (Step 3)
   - Create builder functions that extract only required fields
   - Replace artifact serialization with context builders

3. **Refactor Agents** (Step 4)
   - Update agent signatures to receive context objects
   - Update prompts to use minimal context

4. **Validate** (Step 6)
   - Run tests to ensure outputs remain identical
   - Measure actual token reduction

---

**Report compiled**: 2026-07-26 11:10
