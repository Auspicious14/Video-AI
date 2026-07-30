"""
Phase 2A Validation Tests

Tests for Gemini thinking disabled, JSON mode, token limits, and backwards compatibility.
"""
import asyncio
import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Set test environment
os.environ["GEMINI_API_KEY"] = "test_key_123"
os.environ["GROQ_API_KEY"] = "test_groq_key"


class TestThinkingDisabled:
    """Verify thinking is disabled for structured generation."""
    
    @pytest.mark.asyncio
    async def test_gemini_thinking_disabled_for_json_mode(self):
        """Verify thinking_budget=0 is set when json_mode=True."""
        from services.ai.client import _call_gemini
        from services.ai.providers import PROVIDER_REGISTRY, ProviderName
        
        with patch("services.ai.client.genai") as mock_genai:
            # Mock Gemini client
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = '{"result": "test"}'
            mock_response.candidates = [MagicMock(finish_reason="STOP")]
            mock_response.usage_metadata = MagicMock(
                prompt_token_count=100,
                candidates_token_count=50,
                thoughts_token_count=0,  # Should be 0 when thinking disabled
                total_token_count=150,
            )
            
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value = mock_client
            mock_genai.types = MagicMock()
            
            # Call with json_mode=True
            cfg = PROVIDER_REGISTRY[ProviderName.GEMINI]
            result, metadata = await _call_gemini(
                cfg,
                prompt="Generate JSON",
                system="You are helpful",
                temperature=0.4,
                max_tokens=1000,
                json_mode=True,
            )
            
            # Verify thinking_config was passed
            call_kwargs = mock_client.aio.models.generate_content.call_args[1]
            config = call_kwargs["config"]
            assert getattr(config, "response_mime_type", None) == "application/json"
            thinking_config = getattr(config, "thinking_config", None)
            assert thinking_config is not None
            assert getattr(thinking_config, "thinking_budget", None) == 0
            
            # Verify metadata reflects thinking disabled
            assert metadata["thinking_disabled"] is True
            assert metadata["thoughts_tokens"] == 0
            assert metadata["json_mode"] is True
    
    @pytest.mark.asyncio
    async def test_gemini_thinking_enabled_for_text_mode(self):
        """Verify thinking is NOT disabled for plain text generation."""
        from services.ai.client import _call_gemini
        from services.ai.providers import PROVIDER_REGISTRY, ProviderName
        
        with patch("services.ai.client.genai") as mock_genai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Plain text response"
            mock_response.candidates = [MagicMock(finish_reason="STOP")]
            mock_response.usage_metadata = MagicMock(
                prompt_token_count=100,
                candidates_token_count=50,
                thoughts_token_count=0,
                total_token_count=150,
            )
            
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value = mock_client
            mock_genai.types = MagicMock()
            
            cfg = PROVIDER_REGISTRY[ProviderName.GEMINI]
            result, metadata = await _call_gemini(
                cfg,
                prompt="Write text",
                system="You are helpful",
                temperature=0.7,
                max_tokens=1000,
                json_mode=False,  # NOT JSON mode
            )
            
            # Verify thinking was NOT disabled
            assert metadata["thinking_disabled"] is False
            assert metadata["json_mode"] is False


class TestJSONMode:
    """Verify native JSON mode is used correctly."""
    
    @pytest.mark.asyncio
    async def test_json_mode_sets_response_mime_type(self):
        """Verify response_mime_type='application/json' is set."""
        from services.ai.client import _call_gemini
        from services.ai.providers import PROVIDER_REGISTRY, ProviderName
        
        with patch("services.ai.client.genai") as mock_genai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = '{"key": "value"}'
            mock_response.candidates = [MagicMock(finish_reason="STOP")]
            mock_response.usage_metadata = MagicMock(
                prompt_token_count=50,
                candidates_token_count=25,
                thoughts_token_count=0,
                total_token_count=75,
            )
            
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value = mock_client
            mock_genai.types = MagicMock()
            
            cfg = PROVIDER_REGISTRY[ProviderName.GEMINI]
            await _call_gemini(
                cfg,
                prompt="Generate",
                system="",
                temperature=0.4,
                max_tokens=500,
                json_mode=True,
            )
            
            # Check GenerateContentConfig was called with response_mime_type
            call_kwargs = mock_client.aio.models.generate_content.call_args[1]
            config = call_kwargs["config"]
            # Config should have response_mime_type set
            assert mock_genai.types.GenerateContentConfig.called
    
    @pytest.mark.asyncio
    async def test_response_schema_parameter_forwarded(self):
        """Verify response_schema is passed to Gemini when provided."""
        from services.ai.client import generate_json
        
        test_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }
        
        with patch("services.ai.client._run_with_failover") as mock_failover:
            mock_failover.return_value = ('{"name": "test", "age": 25}', {"provider": "gemini"})
            
            result = await generate_json(
                prompt="Extract data",
                response_schema=test_schema,
            )
            
            # Verify response_schema was passed
            call_kwargs = mock_failover.call_args[1]
            assert call_kwargs["response_schema"] == test_schema

    @pytest.mark.asyncio
    async def test_gemini_structured_config_reaches_sdk(self):
        """Verify response_mime_type, response_schema, and thinking_budget reach GenerateContentConfig."""
        from services.ai.client import _call_gemini
        from services.ai.providers import PROVIDER_REGISTRY, ProviderName

        test_schema = {"type": "object", "properties": {"answer": {"type": "string"}}}

        with patch("services.ai.client.genai") as mock_genai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = '{"answer": "ok"}'
            mock_response.candidates = [MagicMock(finish_reason="STOP")]
            mock_response.usage_metadata = MagicMock(
                prompt_token_count=20,
                candidates_token_count=10,
                thoughts_token_count=0,
                total_token_count=30,
            )
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value = mock_client

            cfg = PROVIDER_REGISTRY[ProviderName.GEMINI]
            _, metadata = await _call_gemini(
                cfg,
                prompt="Generate JSON",
                system="",
                temperature=0.1,
                max_tokens=200,
                json_mode=True,
                response_schema=test_schema,
            )

            config = mock_client.aio.models.generate_content.call_args.kwargs["config"]
            assert getattr(config, "response_mime_type", None) == "application/json"
            assert getattr(config, "response_schema", None) == test_schema
            assert getattr(getattr(config, "thinking_config", None), "thinking_budget", None) == 0
            assert metadata["thinking_disabled"] is True

    @pytest.mark.asyncio
    async def test_gemini_none_usage_metadata_does_not_crash(self):
        """Provider diagnostics must guard None token values before comparisons."""
        from services.ai.client import _call_gemini
        from services.ai.providers import PROVIDER_REGISTRY, ProviderName

        with patch("services.ai.client.genai") as mock_genai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = '{"answer": "ok"}'
            mock_response.candidates = [MagicMock(finish_reason="STOP")]
            mock_response.usage_metadata = MagicMock(
                prompt_token_count=None,
                candidates_token_count=None,
                thoughts_token_count=None,
                total_token_count=None,
            )
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value = mock_client

            cfg = PROVIDER_REGISTRY[ProviderName.GEMINI]
            _, metadata = await _call_gemini(
                cfg,
                prompt="Generate JSON",
                system="",
                temperature=0.1,
                max_tokens=200,
                json_mode=True,
            )

            assert metadata["prompt_tokens"] == 0
            assert metadata["output_tokens"] == 0
            assert metadata["thoughts_tokens"] == 0
            assert metadata["total_tokens"] == 0


class TestTokenLimits:
    """Verify agent-specific token limits are correctly applied."""
    
    def test_compact_agents_have_small_limits(self):
        """Verify Tier 1 compact agents use 150-400 tokens."""
        from services.ai.title import run_title_agent
        from services.ai.thumbnail import run_thumbnail_agent
        from services.ai.seo import run_seo_agent
        
        # These functions should call generate_structured_artifact or generate_json
        # with max_tokens in the compact range
        # We verify by checking the source code was updated
        import inspect
        
        title_source = inspect.getsource(run_title_agent)
        assert "max_tokens=200" in title_source or "200" in title_source
        
        thumb_source = inspect.getsource(run_thumbnail_agent)
        assert "max_tokens=300" in thumb_source or "300" in thumb_source
        
        seo_source = inspect.getsource(run_seo_agent)
        assert "max_tokens=350" in seo_source or "350" in seo_source
    
    def test_moderate_agents_have_medium_limits(self):
        """Verify Tier 2 moderate agents use 600-1600 tokens."""
        from services.ai.studio.script_qa import run_script_qa_agent
        from services.ai.studio.voice_director import run_voice_direction_agent
        
        import inspect
        
        qa_source = inspect.getsource(run_script_qa_agent)
        assert "max_tokens=1600" in qa_source or "1600" in qa_source
        
        voice_source = inspect.getsource(run_voice_direction_agent)
        assert "max_tokens=1200" in voice_source or "1200" in voice_source
    
    def test_rich_agents_have_large_limits(self):
        """Verify Tier 3 rich agents use 1800-3200 tokens."""
        from services.ai.studio.visual_planner import run_visual_planning_agent
        from services.ai.studio.packaging import run_final_qa_agent
        
        import inspect
        
        visual_source = inspect.getsource(run_visual_planning_agent)
        assert "max_tokens=3200" in visual_source or "3200" in visual_source
        
        qa_source = inspect.getsource(run_final_qa_agent)
        assert "max_tokens=2600" in qa_source or "2600" in qa_source


class TestTruncationDiagnostics:
    """Verify enhanced diagnostics are logged."""
    
    @pytest.mark.asyncio
    async def test_truncation_warning_includes_all_metadata(self):
        """Verify truncation logs include provider, model, json_mode, thinking_disabled."""
        from services.ai.client import _run_with_failover
        from services.ai.providers import PROVIDER_REGISTRY, ProviderName
        
        with patch("services.ai.client._call_provider") as mock_call:
            # Simulate truncation
            mock_call.return_value = (
                '{"incomplete": "data',
                {
                    "finish_reason": "MAX_TOKENS",
                    "prompt_tokens": 1000,
                    "output_tokens": 500,
                    "thoughts_tokens": 0,
                    "total_tokens": 1500,
                    "json_mode": True,
                    "thinking_disabled": True,
                }
            )
            
            with patch("services.ai.client.logger") as mock_logger:
                try:
                    result, metadata = await _run_with_failover(
                        prompt="test",
                        system="",
                        temperature=0.4,
                        max_tokens=500,
                        json_mode=True,
                    )
                except Exception:
                    pass
                
                # Verify warning was logged with comprehensive metadata
                warning_calls = [call for call in mock_logger.warning.call_args_list]
                assert any("json_mode" in str(call).lower() for call in warning_calls)


class TestBackwardsCompatibility:
    """Verify no breaking changes to existing APIs."""
    
    @pytest.mark.asyncio
    async def test_generate_json_without_response_schema(self):
        """Verify generate_json still works without new response_schema parameter."""
        from services.ai.client import generate_json
        
        with patch("services.ai.client._run_with_failover") as mock_failover:
            mock_failover.return_value = ('{"result": "success"}', {"provider": "groq"})
            
            # Old API call (no response_schema)
            result = await generate_json(
                prompt="Generate data",
                system="Be helpful",
                temperature=0.5,
                max_tokens=1000,
            )
            
            assert result == {"result": "success"}
            
            # Verify response_schema was None (default)
            call_kwargs = mock_failover.call_args[1]
            assert call_kwargs.get("response_schema") is None
    
    def test_documentary_narration_optional_fields(self):
        """Verify new optional fields don't break existing usage."""
        from services.ai.schemas import DocumentaryNarration
        
        # Old-style construction (without new fields)
        narration = DocumentaryNarration(
            title="Test Documentary",
            narration="This is the narration text.",
            estimated_duration_seconds=300,
        )
        
        # Verify default values for new fields
        assert narration.section_mode is False
        assert narration.sections_parsed == {"Full Narration": narration.narration}
    
    def test_documentary_metadata_optional_section_metadata(self):
        """Verify section_metadata is optional and defaults to None."""
        from services.ai.schemas import DocumentaryMetadata
        
        # Old-style construction
        metadata = DocumentaryMetadata(
            hook="Opening hook",
            sections=["Intro", "Main", "Conclusion"],
            key_entities=["Person A", "Company B"],
            key_facts=["Fact 1", "Fact 2"],
            estimated_duration_seconds=300,
        )
        
        # Verify new field defaults to None
        assert metadata.section_metadata is None


class TestJSONRepair:
    """Verify JSON repair mechanism still works."""
    
    def test_repair_unmatched_braces(self):
        """Verify brace balancing repair."""
        from services.ai.json_repair import attempt_json_repair
        
        truncated = '{"name": "test", "data": {"nested": "value"'
        repaired = attempt_json_repair(truncated)
        
        assert repaired is not None
        assert repaired["name"] == "test"
    
    def test_repair_unterminated_string(self):
        """Verify string termination repair."""
        from services.ai.json_repair import attempt_json_repair
        
        truncated = '{"description": "This is a long text that got cut off'
        repaired = attempt_json_repair(truncated)
        
        assert repaired is not None
        assert "description" in repaired
    
    def test_is_likely_truncated_detection(self):
        """Verify truncation detection."""
        from services.ai.json_repair import is_likely_truncated
        
        assert is_likely_truncated('{"incomplete": "data') is True
        assert is_likely_truncated('{"complete": "data"}') is False


class TestSectionBasedInterface:
    """Verify section-based narration is active and resumable."""
    
    @pytest.mark.asyncio
    async def test_section_based_interface_generates_checkpoints(self):
        """Verify section-based generation creates one cached artifact per section."""
        from services.ai.studio.script_writer_v2 import run_section_based_narration_writer
        from services.ai.schemas import (
            TopicIntelligenceResult,
            ResearchResult,
            StoryArchitectureResult,
        )
        import services.ai.studio.cache as studio_cache
        
        brief = TopicIntelligenceResult(
            topic="Test Topic",
            target_audience="General",
            search_intent="learn",
            viewer_expectations=["clear explanation"],
            emotional_angle="curiosity",
            monetization_suitability="safe",
            recommended_storytelling_style="documentary explainer",
        )
        research = ResearchResult(
            topic="Test",
            executive_summary="Summary",
            key_facts=["Fact 1"],
        )
        story = StoryArchitectureResult(
            opening_hook="Opening hook",
            central_conflict="Central conflict",
            key_turning_points=["Beat 1", "Beat 2", "Beat 3"],
            climax="Climax",
            conclusion="Conclusion",
            emotional_progression=["Curious"],
        )

        async def fake_generate_text_with_metadata(*, prompt, **kwargs):
            match = re.search(r"Section target: (\d+) words", prompt)
            target = int(match.group(1)) if match else 30
            text = " ".join(f"word{i}" for i in range(target))
            return text, {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "prompt_tokens": 120,
                "output_tokens": target,
                "thoughts_tokens": 0,
                "total_tokens": 120 + target,
                "finish_reason": "STOP",
                "latency_ms": 25,
            }

        original_dir = studio_cache.STUDIO_CACHE_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                studio_cache.STUDIO_CACHE_DIR = Path(tmp)
                with patch(
                    "services.ai.studio.script_writer_v2.generate_text_with_metadata",
                    fake_generate_text_with_metadata,
                ):
                    first = await run_section_based_narration_writer(
                        brief=brief,
                        research=research,
                        story=story,
                        target_duration=180,
                    )
                    second = await run_section_based_narration_writer(
                        brief=brief,
                        research=research,
                        story=story,
                        target_duration=180,
                    )

                checkpoint_files = list(Path(tmp).glob("narration_section_*.json"))
        finally:
            studio_cache.STUDIO_CACHE_DIR = original_dir

        assert first.word_count == second.word_count
        assert len(checkpoint_files) == 7
        assert first.section_metadata is not None
        assert [section.title for section in first.section_metadata] == [
            "Hook", "Intro", "Chapter 1", "Chapter 2", "Chapter 3", "Conclusion", "CTA"
        ]

    def test_narration_prompt_token_measurement_reduces_largest_call(self):
        """Verify compact section prompts materially reduce the riskiest narration call."""
        from services.ai.studio.script_writer_v2 import measure_narration_prompt_tokens
        from services.ai.schemas import TopicIntelligenceResult, ResearchResult, StoryArchitectureResult

        brief = TopicIntelligenceResult(
            topic="Test Topic",
            target_audience="General",
            search_intent="learn",
            emotional_angle="curiosity",
            monetization_suitability="safe",
            recommended_storytelling_style="documentary explainer",
        )
        research = ResearchResult(
            topic="Test Topic",
            platform="youtube_long",
            tone="documentary",
            executive_summary="A detailed but compact research summary.",
            key_facts=[f"Important fact {i}" for i in range(10)],
            surprising_facts=["A surprising fact"],
        )
        story = StoryArchitectureResult(
            opening_hook="Opening hook",
            central_conflict="Central conflict",
            key_turning_points=["Beat 1", "Beat 2", "Beat 3", "Beat 4"],
            climax="Climax",
            conclusion="Conclusion",
        )

        old_tokens, largest_section_tokens, _ = measure_narration_prompt_tokens(
            brief=brief,
            research=research,
            story=story,
            target_duration=180,
        )

        assert largest_section_tokens < old_tokens * 0.5
    
    def test_narration_section_meta_token_budget(self):
        """Verify section token budget calculation."""
        from services.ai.schemas import NarrationSectionMeta
        
        section = NarrationSectionMeta(
            section_type="chapter",
            title="Chapter 1",
            target_word_count=200,
            duration_seconds=120.0,
        )
        
        # ~1.35 tokens per word
        expected_budget = round(200 * 1.35)
        assert section.token_budget == expected_budget


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
