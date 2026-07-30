"""End-to-end tests for sectioned narration generation without real providers."""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test_key")
os.environ.setdefault("GROQ_API_KEY", "test_key")

from services.ai.schemas import (  # noqa: E402
    DocumentaryMetadata,
    ResearchResult,
    StoryArchitectureResult,
    TopicIntelligenceResult,
)
from services.ai.studio.script_writer_v2 import run_documentary_script_writer_agent  # noqa: E402
import services.ai.studio.cache as studio_cache  # noqa: E402


class TestSectionedNarrationEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_180_second_script_writer_uses_section_checkpoints(self) -> None:
        brief = TopicIntelligenceResult(
            topic="The hidden history of electric cars",
            target_audience="Curious technology viewers",
            search_intent="Understand why electric cars took so long to arrive",
            viewer_expectations=["clear timeline", "surprising historical context"],
            emotional_angle="curiosity",
            monetization_suitability="brand safe",
            recommended_storytelling_style="documentary explainer",
        )
        research = ResearchResult(
            topic="The hidden history of electric cars",
            platform="youtube_long",
            tone="documentary",
            executive_summary=(
                "Electric cars are often framed as a modern invention, but battery vehicles "
                "competed with petrol cars in the earliest era of motoring."
            ),
            key_facts=[
                "Electric vehicles existed in the late nineteenth and early twentieth centuries.",
                "Early electric cars were quiet and simple compared with many petrol vehicles.",
                "Battery limits and fuel infrastructure shaped the market for decades.",
                "Modern lithium-ion batteries changed the economics of electric cars.",
            ],
            surprising_facts=["Electric taxis operated in some cities before petrol cars dominated."],
        )
        story = StoryArchitectureResult(
            opening_hook="Electric cars did not suddenly appear in the twenty-first century.",
            central_conflict="The technology was promising early, but infrastructure and batteries held it back.",
            key_turning_points=[
                "The first wave of early electric vehicles",
                "The rise of cheap petrol and mass manufacturing",
                "The battery breakthrough that reopened the race",
            ],
            climax="The comeback was not one invention, but a stack of economic and technical shifts.",
            conclusion="The electric car story is less about novelty than timing.",
        )

        async def fake_generate_text_with_metadata(*, prompt, **kwargs):
            match = re.search(r"Section target: (\d+) words", prompt)
            target = int(match.group(1)) if match else 40
            section = re.search(r"Section: ([^(]+)", prompt)
            section_name = section.group(1).strip().lower().replace(" ", "_") if section else "section"
            words = [f"{section_name}_{idx}" for idx in range(target)]
            return " ".join(words), {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "prompt_tokens": 160,
                "output_tokens": target,
                "thoughts_tokens": 0,
                "total_tokens": 160 + target,
                "finish_reason": "STOP",
                "latency_ms": 10,
            }

        async def fake_metadata(*, narration, research):
            return DocumentaryMetadata(
                hook="Electric cars did not suddenly appear.",
                sections=["Hook", "Intro", "Chapter 1", "Chapter 2", "Chapter 3", "Conclusion", "CTA"],
                key_entities=["Electric cars"],
                key_facts=research.key_facts[:3],
                chapters=["0:00 Hook"],
                source_notes=["Research package"],
                estimated_duration_seconds=narration.estimated_duration_seconds,
                section_metadata=narration.section_metadata,
            )

        original_dir = studio_cache.STUDIO_CACHE_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                studio_cache.STUDIO_CACHE_DIR = Path(tmp)
                with patch(
                    "services.ai.studio.script_writer_v2.generate_text_with_metadata",
                    fake_generate_text_with_metadata,
                ), patch(
                    "services.ai.studio.script_writer_v2.run_metadata_extractor_agent",
                    fake_metadata,
                ):
                    result = await run_documentary_script_writer_agent(
                        brief=brief,
                        research=research,
                        story=story,
                        target_duration=180,
                    )
                    checkpoint_count = len(list(Path(tmp).glob("narration_section_*.json")))
        finally:
            studio_cache.STUDIO_CACHE_DIR = original_dir

        self.assertEqual(checkpoint_count, 7)
        self.assertGreaterEqual(len(result.narration.split()), 413)
        self.assertLessEqual(len(result.narration.split()), 457)
        self.assertEqual(result.estimated_duration_seconds, 180)
        self.assertIn("hook_0", result.narration)
        self.assertIn("chapter_2_0", result.narration)


if __name__ == "__main__":
    unittest.main()
