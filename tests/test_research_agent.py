"""
tests/test_research_agent.py — Unit Tests for the Research Intelligence Agent

This test suite verifies:
1. Robust validation and schema enforcement of ResearchResult.
2. The 10-step repair and coercion system (handling legacy array shapes).
3. The prompt template loading and variable interpolation.
4. Formatting utilities (summary, context, hook, and risk serializers).
5. Integration with the AI abstraction via provider mocking.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai.exceptions import ValidationError
from services.ai.prompts import load_prompt
from services.ai.research import (
    research_hooks_summary,
    research_risks_summary,
    research_to_context,
    research_to_summary,
    run_research,
)
from services.ai.schemas import ResearchResult, VisualType, RiskType, SourceType


class TestResearchAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.mock_raw_data = {
            "topic": "Postpartum depression in Nigeria",
            "platform": "tiktok",
            "tone": "empathetic",
            "executive_summary": "A deep look at postpartum depression, affecting 1 in 5 new mothers in Nigeria.",
            "key_facts": [
                "Fact 1: It is often undiagnosed.",
                "Fact 2: Cultural stigma prevents seeking help.",
                "Fact 3: Traditional practices sometimes worsen it.",
                "Fact 4: 15-20% of new mothers experience it.",
                "Fact 5: It is different from 'baby blues'.",
                "Fact 6: Partner support reduces symptoms.",
                "Fact 7: Lack of sleep is a major trigger.",
                "Fact 8: Professional counseling is highly effective."
            ],
            "timeline": [
                "2020: National maternal mental health guidelines introduced.",
                "2023: First community support network launched in Lagos."
            ],
            "surprising_facts": [
                "Traditional birth attendants are being trained to spot early signs.",
                "Many fathers experience paternal postpartum depression too."
            ],
            "misconceptions": [
                "Myth: It is caused by spiritual attacks. Reality: It is a clinical hormonal and mental condition.",
                "Myth: Good mothers do not get depressed. Reality: It can affect anyone regardless of love for the child."
            ],
            "interesting_stats": [
                "According to WHO, African women show higher rates of perinatal depression.",
                "NBS reports less than 10% of affected women gain access to maternal mental health care."
            ],
            "emotional_angles": [
                {"angle": "empathetic", "description": "Resonating with new mother struggles.", "example_hook": "To every new mum feeling alone right now — we see you."},
                {"angle": "caution", "description": "Spotting the differences from normal fatigue.", "example_hook": "Is it just mother exhaustion, or is it something deeper?"}
            ],
            "hook_opportunities": [
                {"hook": "She thought it was just the stress of a newborn.", "angle": "suspense", "strength": 9.2},
                {"hook": "Why do we keep quiet about maternal depression in Nigeria?", "angle": "curiosity", "strength": 8.8}
            ],
            "suggested_hook_angles": [
                "She thought it was just the stress of a newborn.",
                "Why do we keep quiet about maternal depression in Nigeria?"
            ],
            "visual_opportunities": [
                {"concept": "A room with morning light, a woman staring out the window.", "visual_type": "ai_image", "description": "Cinematic side profile of a Nigerian woman holding a sleeping baby.", "scene_moment": "Opening narration about quiet struggles."},
                {"concept": "Stats chart rising.", "visual_type": "chart", "description": "Simple clean bar chart showing depression percentage.", "scene_moment": "Statistical overview."}
            ],
            "search_keywords": ["maternal mental health", "postpartum depression Nigeria"],
            "related_topics": [
                {"topic": "Paternal postpartum depression", "relevance": "Dads get it too.", "content_angle": "Documentary storytelling"}
            ],
            "reliable_sources": [
                {"name": "WHO Perinatal Health Guidelines", "type": "ngo", "relevance": "Global stats and risk factors"},
                {"name": "NCDC", "type": "government", "relevance": "Local health trends"}
            ],
            "risk_flags": [
                {"risk_type": "medical_advice", "description": "Topic touches on mental health medication.", "mitigation": "Add disclaimer: Seek help from a certified therapist."}
            ],
            "content_angles": {
                "tiktok_short": "Focus on the visual contrast of baby blues and postpartum depression.",
                "youtube_long": "Expose the systemic lack of psychiatric care for new mothers."
            },
            "audience_insights": {
                "primary_pain_points": ["Fear of being judged as an incapable mother."],
                "common_questions": ["Is postpartum depression real?"],
                "emotional_triggers": ["Feeling isolated amidst cultural celebrations."],
                "cultural_context": "In many Nigerian settings, new mothers are expected to show only joy."
            },
            "content_warnings": [
                "Contains discussions of maternal mental health struggles."
            ]
        }

    def test_schema_validates_correct_structure(self) -> None:
        """Verify that a conforms-to-spec raw dictionary validates successfully."""
        result = ResearchResult.model_validate(self.mock_raw_data)
        self.assertEqual(result.topic, "Postpartum depression in Nigeria")
        self.assertEqual(result.platform, "tiktok")
        self.assertEqual(len(result.key_facts), 8)
        self.assertEqual(result.hook_opportunities[0].strength, 9.2)
        self.assertTrue(result.has_risks)
        self.assertEqual(result.best_hooks[0], "She thought it was just the stress of a newborn.")

    def test_schema_allows_extra_fields(self) -> None:
        """Verify forward compatibility: new fields in JSON must not raise errors."""
        data_with_extra = self.mock_raw_data.copy()
        data_with_extra["future_schema_field_v3"] = "some value"
        
        result = ResearchResult.model_validate(data_with_extra)
        self.assertEqual(result.topic, "Postpartum depression in Nigeria")

    def test_repair_engine_coerces_v1_legacy_types(self) -> None:
        """Verify the 10-step repair engine corrects legacy string-array formats to structured models."""
        from services.ai.research import _validate_and_repair
        
        legacy_data = {
            "topic": "Legacy Repaired Topic",
            "executive_summary": "Summary text here.",
            "key_facts": ["Fact 1", "Fact 2"],
            "emotional_angles": ["Angle description 1", "Angle description 2"],
            "visual_opportunities": ["Visual Concept 1", "Visual Concept 2"],
            "related_topics": ["Related Topic 1"],
            "reliable_sources": ["Source 1"],
            "risk_flags": ["Caution: mental health"],
        }
        
        repaired = _validate_and_repair(
            legacy_data,
            topic="Legacy Repaired Topic",
            platform="youtube_long",
            tone="educational"
        )
        
        # Verify identity fields set
        self.assertEqual(repaired.platform, "youtube_long")
        self.assertEqual(repaired.tone, "educational")
        
        # Verify model coercion
        self.assertEqual(repaired.emotional_angles[0].description, "Angle description 1")
        self.assertEqual(repaired.emotional_angles[0].angle, "curiosity")
        
        self.assertEqual(repaired.visual_opportunities[0].concept, "Visual Concept 1")
        self.assertEqual(repaired.visual_opportunities[0].visual_type, VisualType.AI_IMAGE)
        
        self.assertEqual(repaired.related_topics[0].topic, "Related Topic 1")
        self.assertEqual(repaired.reliable_sources[0].name, "Source 1")
        self.assertEqual(repaired.reliable_sources[0].type, SourceType.NEWS)
        
        self.assertEqual(repaired.risk_flags[0].risk_type, RiskType.SENSITIVE_CONTENT)
        self.assertEqual(repaired.risk_flags[0].description, "Caution: mental health")
        
        # Verify backfill of hook angles
        self.assertEqual(len(repaired.suggested_hook_angles), 0) # No hook opportunities to backfill from in this dict, which is normal

    def test_repair_backfills_hooks_if_suggested_empty(self) -> None:
        """Verify hook opportunities are backfilled to suggested_hook_angles if omitted."""
        from services.ai.research import _validate_and_repair

        legacy_data = {
            "topic": "Maternal health",
            "executive_summary": "Factual overview",
            "hook_opportunities": [
                {"hook": "How do you survive a newborn?", "angle": "curiosity", "strength": 8.0}
            ]
        }
        repaired = _validate_and_repair(legacy_data, topic="Maternal health", platform="tiktok", tone="informative")
        self.assertEqual(len(repaired.suggested_hook_angles), 1)
        self.assertEqual(repaired.suggested_hook_angles[0], "How do you survive a newborn?")

    def test_serializers_output_valid_strings(self) -> None:
        """Verify research formatting serializers generate structured, readable text blocks."""
        result = ResearchResult.model_validate(self.mock_raw_data)
        
        # 1. Summary Serializer
        summary = research_to_summary(result)
        self.assertIn("EXECUTIVE SUMMARY:", summary)
        self.assertIn("KEY FACTS:", summary)
        self.assertIn("SURPRISING FACTS:", summary)
        self.assertIn("ai_image", summary)
        self.assertIn("⚠️  RISK FLAGS (handle carefully):", summary)
        
        # 2. Rich Context Serializer
        context = research_to_context(result)
        self.assertIn("TIMELINE:", context)
        self.assertIn("AUDIENCE INSIGHTS:", context)
        self.assertIn("PLATFORM ANGLES:", context)
        self.assertIn("RELIABLE SOURCES:", context)
        
        # 3. Hooks Summary
        hooks = research_hooks_summary(result)
        self.assertIn("TOP HOOKS (by engagement score):", hooks)
        self.assertIn("[suspense | 9.2]", hooks)
        
        # 4. Risks Summary
        risks = research_risks_summary(result)
        self.assertIn("⚠️  CONTENT RISK FLAGS — Handle carefully:", risks)
        self.assertIn("[MEDICAL_ADVICE]", risks)

    @patch("services.ai.research.generate_json", new_callable=AsyncMock)
    @patch("services.ai.research.load_prompt")
    async def test_run_research_agent_integration(self, mock_load_prompt: AsyncMock, mock_generate_json: AsyncMock) -> None:
        """Verify agent logic loads templates, invokes generate_json, and parses response."""
        mock_load_prompt.side_effect = lambda name, **kwargs: f"Loaded template: {name}"
        mock_generate_json.return_value = self.mock_raw_data
        
        result = await run_research(
            topic="Pregnancy health",
            tone="supportive",
            duration=45,
            platform="youtube_long",
            niche_context="nigerian women health guidelines",
            audience_profile="expectant mothers"
        )
        
        self.assertEqual(result.topic, "Postpartum depression in Nigeria") # from mock data
        self.assertEqual(result.platform, "tiktok") # from mock data
        self.assertEqual(result.tone, "empathetic") # from mock data
        
        # Validate that prompt loaded correctly
        mock_load_prompt.assert_any_call("base")
        mock_load_prompt.assert_any_call(
            "research",
            topic="Pregnancy health",
            tone="supportive",
            platform="youtube_long",
            duration=45,
            niche_context="nigerian women health guidelines",
            audience_profile="expectant mothers"
        )


if __name__ == "__main__":
    unittest.main()
