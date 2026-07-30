"""
Unit tests for the AI-first YouTube studio layer.

These tests avoid real provider calls. They verify that the new production
architecture has isolated prompts, deterministic stage caching, and graceful
asset fallback behavior.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai.prompts import load_prompt
from services.ai.schemas import (
    AssetCollectionResult,
    DocumentaryScriptResult,
    ImageGenerationPlanResult,
    ResearchResult,
    ScriptQAResult,
    StoryArchitectureResult,
    TopicIntelligenceResult,
    VisualPlanResult,
    VisualTimelineItem,
    VisualType,
)
from services.ai.exceptions import ValidationError
from services.ai.studio.asset_collection import run_asset_collection_service
from services.ai.studio.cache import get_or_create_artifact
from services.ai.studio.script_qa import run_script_qa_agent
from services.ai.studio.story_architect import run_story_architect_agent
from services.ai.studio.visual_planner import run_image_generation_planner_agent
import services.ai.studio.cache as studio_cache


class TestYouTubeStudio(unittest.IsolatedAsyncioTestCase):
    def test_all_studio_prompts_load(self) -> None:
        prompt_names = [
            "studio_topic_intelligence",
            "studio_story_architect",
            "studio_script_writer",
            "studio_script_qa",
            "studio_visual_planner",
            "studio_image_generation",
            "studio_voice_direction",
            "studio_editing_plan",
            "studio_thumbnail_strategy",
            "studio_title_strategy",
            "studio_final_qa",
        ]

        variables = {
            "topic": "The history of semiconductors",
            "target_platform": "youtube",
            "audience_profile": "Curious technology audience",
            "monetization_goal": "long-term YouTube revenue",
            "target_duration": 600,
            "topic_brief": "Brief",
            "research_context": "Research",
            "story_context": "Story",
            "script_context": "Script",
            "aspect_ratio": "16:9",
            "visual_plan_context": "Visual plan",
            "ai_required_indices": "0, 1",
            "style_reference": "Cinematic documentary realism",
            "narration": "Opening narration for visual planning.",
            "sections": "Opening\nEvidence\nConclusion",
            "hook": "A clear documentary hook.",
            "key_concepts": "Concept one\nConcept two",
            "theme": "A concise documentary theme.",
            "key_facts": "Fact one\nFact two",
            "requested_voice_id": "female_warm",
            "asset_collection_json": "{}",
            "audio_qa_json": "{}",
            "editing_plan_json": "{}",
            "thumbnail_json": "{}",
            "title_json": "{}",
            "seo_json": "{}",
            # Script writer variables
            "target_words": 1450,
            "min_words": 1377,
            "max_words": 1522,
            "length_repair_instruction": "",
            # Script QA variables
            "word_count": 450,
            "expected_min_words": 1377,
            "expected_max_words": 1522,
            "estimated_seconds": 180,
        }

        for name in prompt_names:
            rendered = load_prompt(name, **variables)
            self.assertGreater(len(rendered), 50)

    async def test_stage_cache_reuses_artifact(self) -> None:
        calls = 0
        original_dir = studio_cache.STUDIO_CACHE_DIR

        async def factory():
            nonlocal calls
            calls += 1
            return TopicIntelligenceResult(
                topic="Reusable topic",
                target_audience="Curious viewers",
                search_intent="Understand the subject",
                viewer_expectations=["clear story"],
                educational_depth="intermediate",
                emotional_angle="curiosity",
                monetization_suitability="brand safe",
                recommended_video_length_seconds=600,
                recommended_storytelling_style="documentary explainer",
            )

        with tempfile.TemporaryDirectory() as tmp:
            studio_cache.STUDIO_CACHE_DIR = Path(tmp)
            first = await get_or_create_artifact(
                stage="topic_intelligence",
                payload={"topic": "Reusable topic"},
                model=TopicIntelligenceResult,
                factory=factory,
            )
            second = await get_or_create_artifact(
                stage="topic_intelligence",
                payload={"topic": "Reusable topic"},
                model=TopicIntelligenceResult,
                factory=factory,
            )

        studio_cache.STUDIO_CACHE_DIR = original_dir

        self.assertEqual(first.topic, second.topic)
        self.assertEqual(calls, 1)

    async def test_asset_collection_marks_ai_image_for_generation(self) -> None:
        visual_plan = VisualPlanResult(
            visual_style="Cinematic documentary realism",
            timeline=[
                VisualTimelineItem(
                    index=0,
                    start_seconds=0,
                    end_seconds=6,
                    narration_reference="A hidden system shaped the world.",
                    on_screen="Abstract semiconductor supply chain metaphor",
                    asset_type=VisualType.AI_IMAGE,
                    sourcing_priority="ai_only",
                    search_queries=["semiconductor supply chain"],
                    generation_prompt="Cinematic macro shot of silicon wafers",
                )
            ],
        )

        result = await run_asset_collection_service(visual_plan=visual_plan)

        self.assertIsInstance(result, AssetCollectionResult)
        self.assertEqual(result.selected_assets, [])
        self.assertEqual(result.ai_required_indices, [0])

    async def test_story_architect_falls_back_when_json_is_invalid(self) -> None:
        brief = TopicIntelligenceResult(
            topic="Claude vs ChatGPT",
            target_audience="AI tool users",
            search_intent="Compare which model is better",
            viewer_expectations=["clear comparison", "practical recommendation"],
            educational_depth="intermediate",
            emotional_angle="curiosity",
            monetization_suitability="brand safe",
            recommended_video_length_seconds=720,
            recommended_storytelling_style="documentary explainer",
        )
        research = ResearchResult(
            topic="Claude vs ChatGPT",
            platform="youtube_long",
            tone="documentary",
            executive_summary="A factual comparison of two major AI assistants.",
            key_facts=[
                "Claude is often positioned around long-context analysis.",
                "ChatGPT has a broad ecosystem and multimodal tooling.",
                "Best choice depends on task, workflow, and budget.",
            ],
            surprising_facts=["The best model can change depending on the task rather than a universal ranking."],
            hook_opportunities=[
                {"hook": "The better AI is not always the smartest one.", "angle": "curiosity", "strength": 8.7}
            ],
        )

        async def broken_artifact(**kwargs):
            raise ValidationError("Response was not valid JSON", raw="{")

        from unittest.mock import patch

        with patch("services.ai.studio.story_architect.generate_structured_artifact", broken_artifact):
            story = await run_story_architect_agent(brief=brief, research=research)

        self.assertIn("better AI", story.opening_hook)
        self.assertGreaterEqual(len(story.key_turning_points), 1)
        self.assertIn("Act 1", story.act_structure[0])

    def test_script_qa_schema_repairs_common_model_slips(self) -> None:
        raw = {
            "approved": True,
            "score": 82,
            "revised_script": {
                "hook": "The better AI is not always the obvious one.",
                "narration": "Claude and ChatGPT are often compared as if there is one universal winner.",
                "sections": "Opening, Comparison, Conclusion",
                "estimated_duration_seconds": 720,
                "source_notes": "Anthropic, OpenAI, Stanford NLP Group",
            },
            "issues": [
                {
                    "severity": "minor",
                    "stage": "script_qa",
                    "issue": "One transition could be smoother.",
                    "recommendation": "Bridge the examples more directly.",
                },
                {
                    "severity": "major",
                    "stage": "script_qa",
                    "issue": "Ending needs a clearer takeaway.",
                    "recommendation": "Add a concise conclusion.",
                },
            ],
            "strengths": "Clear comparison, practical angle",
        }

        result = ScriptQAResult.model_validate(raw)

        self.assertEqual(result.revised_script.source_notes, ["Anthropic", "OpenAI", "Stanford NLP Group"])
        self.assertEqual(result.issues[0].severity, "low")
        self.assertEqual(result.issues[1].severity, "high")
        self.assertEqual(result.strengths, ["Clear comparison", "practical angle"])

    async def test_script_qa_falls_back_when_ai_output_is_invalid(self) -> None:
        script = DocumentaryScriptResult(
            hook="The better AI is not always the obvious one.",
            narration=" ".join(["This comparison depends on task, context, workflow, and evidence."] * 25),
            sections=["Opening", "Evidence", "Conclusion"],
            estimated_duration_seconds=720,
            source_notes=["Research package"],
        )
        research = ResearchResult(
            topic="Claude vs ChatGPT",
            platform="youtube_long",
            tone="documentary",
            executive_summary="A factual comparison of two major AI assistants.",
            key_facts=["Best choice depends on task.", "Both tools have different ecosystems."],
        )
        story = StoryArchitectureResult(
            opening_hook="The better AI is not always the obvious one.",
            central_conflict="There is no universal winner.",
            key_turning_points=["Compare capabilities", "Compare workflows"],
            climax="The best tool depends on the job.",
            conclusion="Pick based on workflow.",
        )

        async def broken_artifact(**kwargs):
            raise ValidationError("ScriptQAResult validation failed", raw="{")

        from unittest.mock import patch

        with patch("services.ai.studio.script_qa.generate_structured_artifact", broken_artifact):
            result = await run_script_qa_agent(script=script, research=research, story=story)

        self.assertTrue(result.approved)
        self.assertEqual(result.revised_script.hook, script.hook)
        self.assertEqual(result.issues[0].stage, "script_qa")

    def test_image_generation_plan_repairs_prompt_only_items(self) -> None:
        raw = {
            "style_reference": "cinematic documentary realism",
            "prompts": [
                {
                    "index": 0,
                    "time": "0.0-10.0s",
                    "prompt": "A cinematic visual of AI systems walking alongside humans",
                    "asset_type": "ai image",
                    "sourcing_priority": "ai",
                    "search_queries": "AI assistant, human collaboration",
                }
            ],
            "negative_prompt": "artifacts",
        }

        result = ImageGenerationPlanResult.model_validate(raw)

        self.assertEqual(result.prompts[0].start_seconds, 0.0)
        self.assertEqual(result.prompts[0].end_seconds, 10.0)
        self.assertIn("AI systems", result.prompts[0].on_screen)
        self.assertIn("AI systems", result.prompts[0].narration_reference)
        self.assertEqual(result.prompts[0].asset_type, VisualType.AI_IMAGE)
        self.assertEqual(result.prompts[0].sourcing_priority, "ai_only")

    async def test_image_generation_planner_falls_back_to_visual_timeline(self) -> None:
        visual_plan = VisualPlanResult(
            visual_style="cinematic documentary realism",
            timeline=[
                VisualTimelineItem(
                    index=0,
                    start_seconds=0,
                    end_seconds=8,
                    narration_reference="AI assistants became everyday tools.",
                    on_screen="A desk with multiple AI assistant interfaces open",
                    asset_type=VisualType.AI_IMAGE,
                    sourcing_priority="ai_only",
                    search_queries=["AI assistant interface"],
                    generation_prompt="Realistic desk with AI assistant dashboards",
                )
            ],
        )

        async def broken_artifact(**kwargs):
            raise ValidationError("ImageGenerationPlanResult validation failed", raw="{")

        from unittest.mock import patch

        with patch("services.ai.studio.visual_planner.generate_structured_artifact", broken_artifact):
            result = await run_image_generation_planner_agent(
                visual_plan=visual_plan,
                ai_required_indices=[0],
            )

        self.assertEqual(len(result.prompts), 1)
        self.assertEqual(result.prompts[0].index, 0)
        self.assertIn("cinematic", result.prompts[0].generation_prompt.lower())

    async def test_visual_planner_timeline_duration_alignment(self) -> None:
        """Test that visual planner enforces timeline duration to match target."""
        from services.ai.studio.visual_planner import _validate_and_repair_timeline_duration

        # Create a timeline with short beats so pacing doesn't split them
        visual_plan = VisualPlanResult(
            visual_style="documentary",
            timeline=[
                VisualTimelineItem(
                    index=0,
                    start_seconds=0.0,
                    end_seconds=5.0,
                    narration_reference="Opening",
                    on_screen="Hook visual",
                    asset_type=VisualType.AI_IMAGE,
                ),
                VisualTimelineItem(
                    index=1,
                    start_seconds=5.0,
                    end_seconds=10.0,
                    narration_reference="Body",
                    on_screen="Main content",
                    asset_type=VisualType.STOCK_VIDEO,
                ),
                VisualTimelineItem(
                    index=2,
                    start_seconds=10.0,
                    end_seconds=15.0,
                    narration_reference="Conclusion",
                    on_screen="Closing",
                    asset_type=VisualType.AI_IMAGE,
                ),
            ],
        )

        # Target is 30 seconds, current is 15 - should scale by 2x
        target_duration = 30
        result = _validate_and_repair_timeline_duration(visual_plan, target_duration)

        # Check first item starts at 0
        self.assertEqual(result.timeline[0].start_seconds, 0.0)
        # Check last item ends at target duration
        self.assertEqual(result.timeline[-1].end_seconds, float(target_duration))
        # Timeline should cover the full duration
        total_duration = result.timeline[-1].end_seconds - result.timeline[0].start_seconds
        self.assertEqual(total_duration, float(target_duration))

    async def test_visual_planner_timeline_within_tolerance(self) -> None:
        """Test that timeline within tolerance only adjusts edges."""
        from services.ai.studio.visual_planner import _validate_and_repair_timeline_duration

        # Timeline is very close to target (within 2% tolerance)
        # Use shorter beats so pacing improvement doesn't split them
        visual_plan = VisualPlanResult(
            visual_style="documentary",
            timeline=[
                VisualTimelineItem(
                    index=0,
                    start_seconds=0.0,
                    end_seconds=5.0,
                    narration_reference="Part 1",
                    on_screen="Visual 1",
                    asset_type=VisualType.AI_IMAGE,
                ),
                VisualTimelineItem(
                    index=1,
                    start_seconds=5.0,
                    end_seconds=10.0,
                    narration_reference="Part 2",
                    on_screen="Visual 2",
                    asset_type=VisualType.STOCK_VIDEO,
                ),
                VisualTimelineItem(
                    index=2,
                    start_seconds=10.0,
                    end_seconds=14.8,  # Close to 15s total
                    narration_reference="Part 3",
                    on_screen="Visual 3",
                    asset_type=VisualType.AI_IMAGE,
                ),
            ],
        )

        target_duration = 15
        result = _validate_and_repair_timeline_duration(visual_plan, target_duration)

        # Should only adjust edges, not scale (within tolerance)
        self.assertEqual(result.timeline[0].start_seconds, 0.0)
        self.assertEqual(result.timeline[-1].end_seconds, float(target_duration))
        # All beats should be preserved (no splitting since they're all <8s)
        # Note: Timeline might be re-indexed after pacing improvements
        self.assertGreaterEqual(len(result.timeline), 3)

    def test_audio_qa_duration_check(self) -> None:
        """Test that audio QA properly flags duration mismatches."""
        from services.ai.studio.voice_director import run_audio_qa
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Create a dummy audio file
            f.write(b"0" * 10000)
            audio_path = Path(f.name)

        try:
            # Test: audio too short (150s vs 300s expected = 50% = high severity)
            result = run_audio_qa(
                audio_path=audio_path,
                duration_seconds=150.0,  # Actual: 150s
                expected_duration_seconds=300,  # Expected: 300s
            )
            # Should have issues flagged
            self.assertTrue(any("too short" in issue.issue.lower() for issue in result.issues))
            duration_issues = [i for i in result.issues if "too short" in i.issue.lower() or "too long" in i.issue.lower()]
            self.assertGreater(len(duration_issues), 0)

            # Test: audio too long (400s vs 300s expected = 133% = high severity)
            result = run_audio_qa(
                audio_path=audio_path,
                duration_seconds=400.0,  # Actual: 400s
                expected_duration_seconds=300,  # Expected: 300s
            )
            self.assertTrue(any("too long" in issue.issue.lower() for issue in result.issues))

            # Test: audio within tolerance (300s ±5% = 285-315s)
            result = run_audio_qa(
                audio_path=audio_path,
                duration_seconds=295.0,  # Within tolerance
                expected_duration_seconds=300,
            )
            # Should have no duration issues
            duration_issues = [i for i in result.issues if "too short" in i.issue.lower() or "too long" in i.issue.lower()]
            self.assertEqual(len(duration_issues), 0, "Expected no duration issues within tolerance")
        finally:
            audio_path.unlink()


if __name__ == "__main__":
    unittest.main()
