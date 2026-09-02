"""
Stage 4: Separated narration writer and metadata extractor (token-optimized architecture).

This module replaces the monolithic script writer with two specialized agents:

1. Narration Writer: Generates ONLY the spoken narration (plain text, no JSON)
2. Metadata Extractor: Extracts structured metadata FROM the narration (JSON only, no narration)

Token optimization benefit:
- Old: Single agent outputs 2,500+ token JSON (narration + metadata)
- New: Narration writer outputs ~1,800 tokens (text), metadata extractor outputs ~400 tokens (JSON)
- Downstream agents receive only metadata (~400 tokens) instead of full script (~2,500 tokens)
- Total token savings per video: ~60% (from 154,600 to ~60,000)
"""

from __future__ import annotations
from asyncio import protocols
from services.ai.studio.story_architect import story_architecture_context

import logging
from typing import Any
import re
from services.ai.client import generate_text_with_metadata
from services.ai.prompts import load_prompt
from services.ai.schemas import (
    DocumentaryMetadata,
    DocumentaryNarration,
    DocumentaryScriptResult,
    NarrationSectionMeta,
    NarrationSectionResult,
    ResearchResult,
    StoryArchitectureResult,
    TopicIntelligenceResult,
)
from services.ai.studio.cache import artifact_path, cache_key, get_or_create_artifact
from services.ai.studio.context import (
    build_script_writer_context,
    research_brief_context,
    story_context,
    topic_brief_context,
)
from services.ai.studio.duration import estimate_duration_seconds, target_word_count, word_count, word_count_range
from collections import Counter


logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────────
#  Phase 2A: Section-Based Generation Interface (Future Use)
# ────────────────────────────────────────────────────────────────────────────────

_TRUNCATED_REASONS = {"MAX_TOKENS", "length", "FinishReason.MAX_TOKENS"}

WORDS_PER_MINUTE = 145


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))

async def run_section_based_narration_writer(
    *,
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int,
) -> DocumentaryNarration:
    """
    Generate narration section-by-section with resumable cache checkpoints.

    Each section is a plain-text generation call. Completed sections are cached
    independently, so a restart or Chapter 2 retry never regenerates Hook,
    Intro, Chapter 1, or any other completed section.
    """
    context = build_script_writer_context(brief, research, story)
    sections = _build_narration_section_plan(
        brief=brief,
        research=research,
        story=story,
        target_duration=target_duration,
    )
    outline = _format_story_outline(context.story_beats)
    tone = research.tone or brief.emotional_angle or "documentary"

    before_tokens, after_max_tokens, after_total_tokens = measure_narration_prompt_tokens(
        brief=brief,
        research=research,
        story=story,
        target_duration=target_duration,
    )
    logger.info(
        "[Narration Writer] Context audit | old_single_prompt≈%d tokens "
        "new_largest_section≈%d tokens new_all_sections≈%d tokens reduction_vs_single=%.1f%%",
        before_tokens,
        after_max_tokens,
        after_total_tokens,
        _percent_reduction(before_tokens, after_max_tokens),
    )

    generated: list[NarrationSectionResult] = []
    continuity: list[str] = []

    for index, section in enumerate(sections):
        payload = {
            "topic": context.topic,
            "tone": tone,
            "target_duration": target_duration,
            "section_index": index,
            "section": section.model_dump(mode="json"),
            "research_summary": _research_summary_for_prompt(context),
            "story_outline": outline,
            "previous_summaries": continuity[-3:],
        }
        key = cache_key("narration_section", payload)
        path = artifact_path(key)
        cached = path.exists()

        async def factory(section: NarrationSectionMeta = section, index: int = index) -> NarrationSectionResult:
            return await _generate_narration_section(
                context=context,
                section=section,
                section_index=index,
                section_count=len(sections),
                target_duration=target_duration,
                tone=tone,
                story_outline=outline,
                previous_summaries=continuity[-3:],
            )

        result = await get_or_create_artifact(
            stage="narration_section",
            payload=payload,
            model=NarrationSectionResult,
            factory=factory,
        )
        generated.append(result)
        continuity.append(f"{result.section.title}: {result.summary}")

        logger.info(
            "[Narration Section] section=%s provider=%s prompt_tokens=%d output_tokens=%d "
            "thought_tokens=%d finish_reason=%s latency_ms=%d retry_count=%d "
            "checkpoint_saved=%s cached=%s words=%d target_words=%d",
            result.section.title,
            result.provider,
            result.prompt_tokens,
            result.output_tokens,
            result.thoughts_tokens,
            result.finish_reason,
            result.latency_ms,
            result.retry_count,
            path.exists(),
            cached,
            result.actual_word_count,
            result.section.target_word_count,
        )

    narration_text = "\n\n".join(section.narration.strip() for section in generated if section.narration.strip())
    actual_duration = estimate_duration_seconds(narration_text)

    section_metadata = []
    for result in generated:
        meta = result.section.model_copy(
            deep=True,
            update={
                "actual_word_count": result.actual_word_count,
                "provider": result.provider,
                "model": result.model,
                "prompt_tokens": result.prompt_tokens,
                "output_tokens": result.output_tokens,
                "thoughts_tokens": result.thoughts_tokens,
                "total_tokens": result.total_tokens,
                "finish_reason": result.finish_reason,
                "latency_ms": result.latency_ms,
                "retry_count": result.retry_count,
            },
        )
        section_metadata.append(meta)

    logger.info(
        "[Narration Writer] Sectioned narration complete | sections=%d words=%d estimated_duration=%ds target=%ds",
        len(generated),
        word_count(narration_text),
        actual_duration,
        target_duration,
    )

    return DocumentaryNarration(
        title=brief.topic[:80],
        narration=narration_text,
        estimated_duration_seconds=actual_duration,
        section_mode=False,
        section_metadata=section_metadata,
    )


# ────────────────────────────────────────────────────────────────────────────────
#  Current Production Code (Phase 1 Architecture)
# ────────────────────────────────────────────────────────────────────────────────

async def run_narration_writer_agent(
    *,
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int,
) -> DocumentaryNarration:
    """
    Write ONLY the documentary narration (plain text, no JSON).
    
    This agent generates the complete spoken script that will be read aloud.
    It does NOT generate metadata, sections, or any structured fields.
    
    Returns DocumentaryNarration containing only title and narration text.
    """
    return await run_section_based_narration_writer(
        brief=brief,
        research=research,
        story=story,
        target_duration=target_duration,
    )


async def run_metadata_extractor_agent(
    *,
    narration: DocumentaryNarration,
    research: ResearchResult,
) -> DocumentaryMetadata:
    """
    Extract structured metadata FROM the narration (does NOT include narration).
    
    This agent reads the complete narration and extracts:
    - Hook (opening line)
    - Section boundaries
    - Key entities (people, companies, places)
    - Key facts (core insights)
    - Chapter markers (YouTube format)
    - Source notes (citations)
    
    Returns DocumentaryMetadata containing ONLY metadata, NOT the narration itself.
    
    Token optimization: This lightweight agent outputs ~400 tokens instead of
    the 2,500+ tokens that the old combined script writer produced.
    """
    from services.ai.studio.agent_utils import generate_structured_artifact
    
    variables = {
        "narration": narration.narration,
        "research_context": research_brief_context(research, rich=False),
    }
    
    metadata = await generate_structured_artifact(
        prompt_name="studio_metadata_extractor",
        model=DocumentaryMetadata,
        variables=variables,
        temperature=0.24,
        max_tokens=800,  # Phase 2A: Realistic for metadata extraction (~600 tokens typical)
        attempts=2,
    )
    
    # Ensure duration matches narration
    metadata.estimated_duration_seconds = narration.estimated_duration_seconds
    if narration.section_metadata:
        metadata.section_metadata = narration.section_metadata
    
    logger.info(
        f"[Metadata Extractor] ✓ Extracted {len(metadata.sections)} sections, "
        f"{len(metadata.key_entities)} entities, {len(metadata.key_facts)} key facts"
    )
    
    return metadata


async def run_documentary_script_writer_agent(
    *,
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int,
) -> DocumentaryScriptResult:
    """
    LEGACY WRAPPER: Generates script using new separated architecture.
    
    This maintains backwards compatibility with existing pipeline code
    by returning the legacy DocumentaryScriptResult format.
    
    Internally, it calls:
    1. run_narration_writer_agent() → DocumentaryNarration
    2. run_metadata_extractor_agent() → DocumentaryMetadata
    3. Combines them into DocumentaryScriptResult for legacy compatibility
    
    New code should call the separated agents directly to avoid combining artifacts.
    """
    logger.info("[Script Writer] Using separated narration + metadata architecture")
    
    # Step 1: Generate narration (plain text)
    narration = await run_narration_writer_agent(
        brief=brief,
        research=research,
        story=story,
        target_duration=target_duration,
    )
    
    # Step 2: Extract metadata from narration (JSON)
    metadata = await run_metadata_extractor_agent(
        narration=narration,
        research=research,
    )
    
    # Step 3: Combine into legacy format for backwards compatibility
    combined = DocumentaryScriptResult.from_separated(narration, metadata)
    
    logger.info(
        f"[Script Writer] ✓ Combined script: {narration.word_count} words, "
        f"{len(metadata.sections)} sections, {len(metadata.key_facts)} key facts"
    )
    
    return combined


CHAPTER_TARGET_WORDS = 90  # was 55 — fewer, richer chapters instead of many thin ones
MAX_CHAPTERS = 8            # was 14 — a real documentary rarely has more distinct beats than this

def _build_narration_section_plan(
    *,
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int,
) -> list[NarrationSectionMeta]:
    total_words = target_word_count(target_duration)

    fixed_fractions = {"hook": 0.08, "intro": 0.12, "conclusion": 0.10, "cta": 0.05}
    chapter_fraction = 1.0 - sum(fixed_fractions.values())
    chapter_total_words = round(total_words * chapter_fraction)

    # Never manufacture more chapters than there's real distinct story
    # content for — otherwise _split_points duplicates the same few
    # turning points across many near-identical chapters, wasting LLM
    # calls on beats that don't add anything.
    story_beats_available = max(3, len(story.key_turning_points) * 2)
    num_chapters = max(
        3,
        min(MAX_CHAPTERS, story_beats_available, round(chapter_total_words / CHAPTER_TARGET_WORDS)),
    )
    chapter_words = _distribute_words(chapter_total_words, [1.0 / num_chapters] * num_chapters)
    hook_words = round(total_words * fixed_fractions["hook"])
    intro_words = round(total_words * fixed_fractions["intro"])
    conclusion_words = round(total_words * fixed_fractions["conclusion"])
    cta_words = round(total_words * fixed_fractions["cta"])

    story_beats = [story.opening_hook, story.central_conflict, *story.key_turning_points, story.climax, story.conclusion]
    chapter_points = _split_points(story.key_turning_points or story_beats, num_chapters)
    cursor = 0.0

    specs: list[tuple[str, str, int, list[str], str]] = [
        ("hook", "Hook", hook_words,
         [research.best_hooks[0] if research.best_hooks else story.opening_hook], "urgent"),
        ("introduction", "Intro", intro_words,
         [story.opening_hook, story.central_conflict], brief.emotional_angle or "informative"),
    ]
    for i in range(num_chapters):
        specs.append(("chapter", f"Chapter {i + 1}", chapter_words[i], chapter_points[i], "informative"))
    specs.append(("conclusion", "Conclusion", conclusion_words, [story.climax, story.conclusion], "inspiring"))
    specs.append((
        "cta", "CTA", cta_words,
        ["Close with a single understated statement that reinforces the throughline of the piece — no direct address to the viewer, no 'subscribe' language."],
        "hopeful",
    ))

    sections: list[NarrationSectionMeta] = []
    for section_type, title, words, points, tone in specs:
        duration = max(5.0, words * 60 / 145)
        sections.append(NarrationSectionMeta(
            section_type=section_type, title=title, target_word_count=max(1, words),
            start_time_seconds=round(cursor, 2), duration_seconds=round(duration, 2),
            key_points=[point for point in points if point], emotional_tone=tone,
        ))
        cursor += duration
    return sections

def _distribute_words(total_words: int, weights: list[float]) -> list[int]:
    """Round weighted word counts while preserving the exact total."""
    raw = [max(1, round(total_words * weight)) for weight in weights]
    diff = total_words - sum(raw)
    order = sorted(range(len(raw)), key=lambda idx: weights[idx], reverse=True)
    cursor = 0
    while diff != 0 and order:
        idx = order[cursor % len(order)]
        if diff > 0:
            raw[idx] += 1
            diff -= 1
        elif raw[idx] > 1:
            raw[idx] -= 1
            diff += 1
        cursor += 1
    return raw


def _split_points(points: list[str], groups: int) -> list[list[str]]:
    """Split story points across chapter buckets without dropping sparse outlines."""
    cleaned = [point for point in points if point]
    if not cleaned:
        cleaned = ["Develop the core evidence.", "Explain the implications.", "Resolve the story."]
    buckets: list[list[str]] = [[] for _ in range(groups)]
    for index, point in enumerate(cleaned):
        buckets[index % groups].append(point)
    for index, bucket in enumerate(buckets):
        if not bucket:
            bucket.append(cleaned[min(index, len(cleaned) - 1)])
    return buckets


def _is_degenerate_repetition(text: str, max_repeat_ratio: float = 0.3) -> bool:
    """
    Detect repetition-loop garbage (e.g. 'Spotify Spotify Spotify...') that a
    plain word-count check can't catch, because it counts words, not content.
    Conservative on purpose — only flags text where one word dominates far
    beyond anything normal narration would ever produce.
    """
    words = [w.strip(".,!?\"'").lower() for w in text.split() if w.strip(".,!?\"'")]
    if len(words) < 6:
        return False
    most_common_word, count = Counter(words).most_common(1)[0]
    return (count / len(words)) > max_repeat_ratio


async def _generate_narration_section(
    *,
    context: Any,
    section: NarrationSectionMeta,
    section_index: int,
    section_count: int,
    target_duration: int,
    tone: str,
    story_outline: str,
    previous_summaries: list[str],
) -> NarrationSectionResult:
    """Generate one section with independent retries and rich diagnostics."""
    target = section.target_word_count
    min_words = max(1, round(target * 0.85))
    max_words = max(min_words, round(target * 1.15))
    best: NarrationSectionResult | None = None
    retry_note = ""

    for attempt in range(1, 4):
        prompt = _build_section_prompt(
            context=context,
            section=section,
            section_index=section_index,
            section_count=section_count,
            target_duration=target_duration,
            tone=tone,
            story_outline=story_outline,
            previous_summaries=previous_summaries,
            min_words=min_words,
            max_words=max_words,
            retry_note=retry_note,
        )

        was_truncated_last = bool(best) and best.finish_reason in _TRUNCATED_REASONS
        temperature = 0.35 if was_truncated_last else (0.58 if attempt == 1 else 0.60)

        last_narration, metadata = await _generate_section_with_validation(
            prompt=prompt,
            system=(
                "You are a professional documentary narration writer. "
                "Write only spoken narration for the requested section. No JSON."
            ),
            min_words=min_words,
            max_words=max_words,
            temperature=temperature,
            max_tokens=_section_token_budget(section.target_word_count, attempt),
        )
        cleaned = last_narration
        words = word_count(cleaned)
        degenerate = _is_degenerate_repetition(cleaned)

        result = NarrationSectionResult(
            section=section.model_copy(update={"actual_word_count": words}),
            narration=cleaned,
            summary=_continuity_summary(section.title, cleaned),
            actual_word_count=words,
            estimated_duration_seconds=estimate_duration_seconds(cleaned),
            provider=str(metadata.get("provider") or "unknown"),
            model=str(metadata.get("model") or "unknown"),
            prompt_tokens=_metadata_int(metadata, "prompt_tokens"),
            output_tokens=_metadata_int(metadata, "output_tokens"),
            thoughts_tokens=_metadata_int(metadata, "thoughts_tokens"),
            total_tokens=_metadata_int(metadata, "total_tokens"),
            finish_reason=str(metadata.get("finish_reason") or "unknown"),
            latency_ms=_metadata_int(metadata, "latency_ms"),
            retry_count=attempt - 1,
        )

        # Never let a degenerate result become "best" — a repetition loop can
        # accidentally land inside the word-count window and would otherwise
        # get silently preferred over an honest, merely-short attempt.
        if not degenerate and (
            best is None or _section_distance(result.actual_word_count, target) < _section_distance(best.actual_word_count, target)
        ):
            best = result

        truncated = result.finish_reason in _TRUNCATED_REASONS
        if not truncated and not degenerate and min_words <= words <= max_words:
            return result

        if degenerate:
            retry_note = (
                "Previous attempt degenerated into repeating the same word or phrase "
                "over and over. Write normal, varied documentary narration — "
                f"{min_words}-{max_words} words, no repetition."
            )
        elif truncated:
            retry_note = (
                f"Previous attempt was cut off at {words} words with finish_reason={result.finish_reason}. "
                f"Rewrite this same section, complete, at {min_words}-{max_words} words. "
                "Do not continue into the next section."
            )
        elif words > max_words:
            overage = words - max_words
            retry_note = (
                f"Previous attempt was {words} words — {overage} words over the "
                f"{max_words}-word maximum. Cut it down: remove one supporting detail "
                "or tighten the phrasing. Keep the core message intact."
            )
        else:
            shortfall = max(0, min_words - words)
            retry_note = (
                f"Previous attempt was only {words} words — {shortfall} words short of the "
                f"{min_words}-word minimum. Add specific detail: one more concrete fact, "
                "example, or descriptive elaboration from the research summary. "
                "Do not pad with filler or repeat what you already wrote."
            )
        logger.warning(
            "[Narration Section] retrying section=%s attempt=%d words=%d target=%d finish_reason=%s degenerate=%s",
            section.title, attempt, words, target, result.finish_reason, degenerate,
        )

    if best and best.finish_reason not in _TRUNCATED_REASONS:
        if best.actual_word_count < min_words:
            expanded = await _expand_section_narration(
                context=context,
                section=section,
                current=best,
                min_words=min_words,
                max_words=max_words,
                story_outline=story_outline,
            )
            if expanded:
                logger.info(
                    "[Narration Section] expanded section=%s %d -> %d words",
                    section.title, best.actual_word_count, expanded.actual_word_count,
                )
                return expanded
        return best
    raise RuntimeError(f"Narration section {section.title} repeatedly truncated before completion.")


async def _expand_section_narration(
    *,
    context: Any,
    section: NarrationSectionMeta,
    current: NarrationSectionResult,
    min_words: int,
    max_words: int,
    story_outline: str,
) -> NarrationSectionResult | None:
    """
    Cheap final pass: extend existing narration to meet the word floor instead
    of gambling on a full regeneration landing longer. Guards against both
    under-shooting AND the model degenerating into a repetition loop, which
    is longer than the original but is garbage, not real content.
    """
    prompt = "\n".join(
        [
            "Here is one section of a documentary narration that needs to be longer.",
            f"Current length: {current.actual_word_count} words. Target: {min_words}-{max_words} words.",
            "",
            "CURRENT TEXT",
            current.narration,
            "",
            "RESEARCH SUMMARY",
            _research_summary_for_prompt(context),
            "",
            "STORY OUTLINE",
            story_outline,
            "",
            "Expand this to at least " + str(min_words) + " words by adding one or two "
            "concrete facts, examples, or descriptive details drawn from the research "
            "summary above. Keep the same opening and closing sentence, the same meaning, "
            "and the same tone. Do not repeat words or phrases. "
            f"Do not exceed {max_words} words. Return ONLY the full revised narration text, nothing else.",
        ]
    ).strip()

    try:
        text, metadata = await generate_text_with_metadata(
            prompt=prompt,
            system=(
                "You are a professional documentary narration writer. "
                "Write only spoken narration. No JSON, no headings, no commentary."
            ),
            temperature=0.5,
            max_tokens=_section_token_budget(max_words, attempt=1),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Narration Section] expand pass failed for %s: %s", section.title, exc)
        return None

    cleaned = _clean_narration_output(text)
    words = word_count(cleaned)

    # Reject anything shorter than before, wildly over budget, or degenerate —
    # in every one of these cases the original (already validated) text is
    # the safer thing to keep than gambling on this pass.
    absolute_ceiling = max_words * 2
    if words < current.actual_word_count or words > absolute_ceiling or _is_degenerate_repetition(cleaned):
        logger.warning(
            "[Narration Section] expand pass produced unusable output for %s "
            "(words=%d, degenerate=%s) — keeping original",
            section.title, words, _is_degenerate_repetition(cleaned),
        )
        return None

    return NarrationSectionResult(
        section=section.model_copy(update={"actual_word_count": words}),
        narration=cleaned,
        summary=_continuity_summary(section.title, cleaned),
        actual_word_count=words,
        estimated_duration_seconds=estimate_duration_seconds(cleaned),
        provider=str(metadata.get("provider") or "unknown"),
        model=str(metadata.get("model") or "unknown"),
        prompt_tokens=_metadata_int(metadata, "prompt_tokens"),
        output_tokens=_metadata_int(metadata, "output_tokens"),
        thoughts_tokens=_metadata_int(metadata, "thoughts_tokens"),
        total_tokens=_metadata_int(metadata, "total_tokens"),
        finish_reason=str(metadata.get("finish_reason") or "unknown"),
        latency_ms=_metadata_int(metadata, "latency_ms"),
        retry_count=current.retry_count + 1,
    )


def _section_token_budget(target_words: int, attempt: int = 1) -> int:
    """Keep each section comfortably under free-provider limits."""
    base = round(target_words * 1.65) + 140
    return max(220, min(1600, base + ((attempt - 1) * 160)))


def _section_distance(actual: int, target: int) -> int:
    return abs(actual - target)


def _metadata_int(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key, 0)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_section_prompt(
    *,
    context: Any,
    section: NarrationSectionMeta,
    section_index: int,
    section_count: int,
    target_duration: int,
    tone: str,
    story_outline: str,
    previous_summaries: list[str],
    min_words: int,
    max_words: int,
    retry_note: str,
) -> str:
    continuity = "\n".join(f"- {item}" for item in previous_summaries) or "- None. This is the opening section."
    key_points = "\n".join(f"- {point}" for point in section.key_points) or "- Follow the story outline."
    return "\n".join(
        [
            "Write one section of a YouTube documentary narration.",
            "",
            f"Topic: {context.topic}",
            f"Tone: {tone}",
            f"Documentary duration: {target_duration} seconds",
            f"Section: {section.title} ({section_index + 1}/{section_count})",
            f"Section target: {section.target_word_count} words",
            f"Accepted range: {min_words}-{max_words} words",
            f"Section emotional tone: {section.emotional_tone}",
            "",
            "RESEARCH SUMMARY",
            _research_summary_for_prompt(context),
            "",
            "STORY OUTLINE",
            story_outline,
            "",
            "CURRENT SECTION KEY POINTS",
            key_points,
            "",
            "CONTINUITY FROM COMPLETED SECTIONS",
            continuity,
            "",
            "RULES",
            "- Write ONLY spoken narration for this section.",
            "- Do not write a heading, label, bullet list, JSON, timestamps, or production notes.",
            "- Do not repeat completed sections.",
            "- End this section cleanly, without starting the next section.",
            "- Use only facts from the research summary and story outline.",
            "- Every specific number, date, or statistic MUST come directly from the research summary above — never invent, round dramatically, or embellish a figure for effect.",
            "- Include at least one concrete, specific detail from the research (a name, date, place, or number) — do not describe this section only in abstract terms like 'relentless innovation' or 'against all odds'.",
            "- If this is not the opening section, your first sentence should connect naturally to the last point in CONTINUITY FROM COMPLETED SECTIONS — do not start cold as if this were a new, unrelated topic.",
            "- Aim for the upper half of the accepted range, not the minimum.",
            "- Before finishing, check: does this reach at least the minimum word count? If not, add detail rather than stopping early.",
            retry_note,
        ]
    ).strip()

def _research_summary_for_prompt(context: Any) -> str:
    lines = [
        context.summary,
        "",
        "Key facts:",
        *_format_list(context.key_facts[:8]),
    ]
    if context.surprising_facts:
        lines.extend(["", "Surprising facts:", *_format_list(context.surprising_facts[:4])])
    return "\n".join(lines).strip()


def _format_story_outline(story_beats: list[str]) -> str:
    return "\n".join(_format_list(story_beats[:10]))


def _format_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items if item]


def _continuity_summary(section_title: str, narration: str) -> str:
    sentences = [part.strip() for part in narration.replace("\n", " ").split(".") if part.strip()]
    if not sentences:
        return f"{section_title} completed."
    first = sentences[0]
    last = sentences[-1]
    if first == last:
        return first[:240]
    return f"{first[:120]}. Ends on: {last[:120]}."


def measure_narration_prompt_tokens(
    *,
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int,
) -> tuple[int, int, int]:
    """Return approximate old single prompt, new largest section, and new total tokens."""
    old_prompt = _build_legacy_narration_prompt(
        brief=brief,
        research=research,
        story=story,
        target_duration=target_duration,
    )
    context = build_script_writer_context(brief, research, story)
    sections = _build_narration_section_plan(
        brief=brief,
        research=research,
        story=story,
        target_duration=target_duration,
    )
    outline = _format_story_outline(context.story_beats)
    tone = research.tone or brief.emotional_angle or "documentary"
    section_prompts = [
        _build_section_prompt(
            context=context,
            section=section,
            section_index=index,
            section_count=len(sections),
            target_duration=target_duration,
            tone=tone,
            story_outline=outline,
            previous_summaries=[],
            min_words=max(1, round(section.target_word_count * 0.85)),
            max_words=max(1, round(section.target_word_count * 1.15)),
            retry_note="",
        )
        for index, section in enumerate(sections)
    ]
    old_tokens = _approx_tokens(old_prompt)
    per_section = [_approx_tokens(prompt) for prompt in section_prompts]
    return old_tokens, max(per_section), sum(per_section)


def _build_legacy_narration_prompt(
    *,
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int,
) -> str:
    min_words, max_words = word_count_range(target_duration)
    variables = {
        "target_duration": target_duration,
        "target_words": target_word_count(target_duration),
        "min_words": min_words,
        "max_words": max_words,
        "topic_brief": topic_brief_context(brief),
        "research_context": research_brief_context(research, rich=True),
        "story_context": story_architecture_context(story),
        "length_repair_instruction": "",
    }
    return load_prompt("studio_narration_writer", **variables)


def _approx_tokens(text: str) -> int:
    """Cheap, deterministic token estimate for prompt-size comparisons."""
    return max(1, round(len(text) / 4))


def _percent_reduction(before: int, after: int) -> float:
    if before <= 0:
        return 0.0
    return max(0.0, (before - after) / before * 100)


def _narration_token_budget(target_duration: int) -> int:
    """
    Calculate token budget for narration generation.
    
    Roughly 1.35 tokens per spoken word (accounting for connector words and natural speech).
    """
    words = target_word_count(target_duration)
    return max(1200, min(8000, round(words * 1.35)))


def _clean_narration_output(text: str) -> str:
    """
    Clean up narration output to remove accidental formatting artifacts.
    
    Some models may add markdown code fences, YAML front matter, or other
    structured formatting despite being told to output plain text.
    """
    text = text.strip()
    
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    # Remove YAML front matter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()
    
    # Remove common section headers that shouldn't be in narration
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line_lower = line.strip().lower()
        # Skip lines that look like metadata headers
        if line_lower in {"narration:", "script:", "title:", "voiceover:", "transcript:"}:
            continue
        cleaned_lines.append(line)
    
    text = "\n".join(cleaned_lines).strip()
    
    return text


async def _generate_section_with_validation(
    *,
    prompt: str,
    system: str,
    min_words: int,
    max_words: int,
    temperature: float = 0.55,
    max_tokens: int = 1800,
) -> tuple[str, dict[str, Any]]:
    """
    Single generation call. Retries, degenerate-repetition rejection, and
    differentiated repair instructions are already owned by the caller
    (_generate_narration_section) — this used to run its own internal
    3-attempt loop on top of that, meaning one section could trigger up to
    9 real LLM calls before giving up. Removed: retry logic now lives in
    exactly one place.
    """
    text, metadata = await generate_text_with_metadata(
        prompt=prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return _clean_narration_output(text), metadata