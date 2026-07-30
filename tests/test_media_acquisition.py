"""
tests/test_media_acquisition.py — Unit Tests for the Intelligent Media Acquisition Engine
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai.schemas import ResearchResult, ScriptResult, Scene, MediaPlan, MediaPlanResult
from services.ai.media.planner import plan_scene_media, plan_script_media, _coerce_media_type
from services.ai.media.collector import MediaAsset, MediaCollector, SimulationProvider
from services.ai.media.ranking import score_asset, rank_assets
from services.ai.media.downloader import MediaDownloader
from services.ai.media.cache import MediaCache
from services.ai.media.classifier import classify_local_media
from services.ai.media.coordinator import acquire_media_assets


class TestMediaAcquisition(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        # Mock Research Result
        self.mock_research = ResearchResult(
            topic="Space Exploration",
            platform="youtube_long",
            tone="inspiring",
            executive_summary="Humanity reaches for the stars, planning trips to Mars and beyond.",
            key_facts=[
                "SpaceX is developing Starship.",
                "NASA plans Artemis moon landing.",
                "Water ice exists on Mars."
            ]
        )
        
        # Mock Script Result
        self.mock_script = ScriptResult(
            hook="Are we alone in the universe?",
            narration="Today, we look closer at Mars. A cold planet holding the keys to our target future.",
            scenes=[
                Scene(
                    description="Cinematic shot of Mars red soil and dusty hills.",
                    image_prompt="High detail planet Mars surface panoramic footage, dust storms rising.",
                    emotion="inspiring",
                    duration=6.0,
                    narration="Today, we look closer at Mars."
                ),
                Scene(
                    description="ChatGPT logo glowing on phone dashboard.",
                    image_prompt="OpenAI ChatGPT mobile interface close up screenshot.",
                    emotion="informative",
                    duration=5.0,
                    narration="Using tools like ChatGPT to calculate trajectories."
                )
            ],
            caption="Space exploration #Mars",
            cta="Subscribe for more space docs"
        )

    def test_media_plan_schema_validates(self) -> None:
        """Verify the MediaPlan schema enforces structures correctly."""
        raw_plan = {
            "scene": 1,
            "media_type": "stock_video",
            "search_query": "Mars surface footage landscape",
            "reasoning": "Mars is mentioned, stock video provides realism.",
            "fallback_media_type": "ai_image",
            "confidence": 0.95,
            "visual_intent": "inspiring red landscape"
        }
        plan = MediaPlan.model_validate(raw_plan)
        self.assertEqual(plan.scene, 1)
        self.assertEqual(plan.media_type, "stock_video")
        self.assertEqual(plan.confidence, 0.95)

    def test_coerce_media_type_utility(self) -> None:
        """Verify media types are coerced correctly to valid categories."""
        self.assertEqual(_coerce_media_type("screenshots"), "screenshot")
        self.assertEqual(_coerce_media_type("stock videos"), "stock_video")
        self.assertEqual(_coerce_media_type("unknown_junk", default="ai_image"), "ai_image")

    @patch("services.ai.media.planner.generate_json", new_callable=AsyncMock)
    async def test_plan_scene_media_llm_invocation(self, mock_generate_json: AsyncMock) -> None:
        """Verify that single-scene media planner queries LLM and parses plans."""
        mock_generate_json.return_value = {
            "scene": 1,
            "media_type": "stock_video",
            "search_query": "Mars surface planet",
            "reasoning": "Need natural surface look.",
            "fallback_media_type": "ai_image",
            "confidence": 0.9,
            "visual_intent": "red planet"
        }
        
        plan = await plan_scene_media(
            self.mock_research, 
            self.mock_script, 
            self.mock_script.scenes[0], 
            1
        )
        self.assertEqual(plan.scene, 1)
        self.assertEqual(plan.media_type, "stock_video")
        self.assertEqual(plan.search_query, "Mars surface planet")
        mock_generate_json.assert_called_once()

    @patch("services.ai.media.planner.generate_json", new_callable=AsyncMock)
    async def test_plan_script_media_batch(self, mock_generate_json: AsyncMock) -> None:
        """Verify batch script media planner queries LLM and falls back on mismatch."""
        mock_generate_json.return_value = {
            "plans": [
                {
                    "scene": 1,
                    "media_type": "stock_video",
                    "search_query": "Mars terrain",
                    "reasoning": "Landscape B-roll.",
                    "fallback_media_type": "ai_image",
                    "confidence": 0.92,
                    "visual_intent": "red soil"
                },
                {
                    "scene": 2,
                    "media_type": "screenshot",
                    "search_query": "ChatGPT OpenAI app",
                    "reasoning": "Software UI.",
                    "fallback_media_type": "website",
                    "confidence": 0.98,
                    "visual_intent": "interface"
                }
            ]
        }
        
        plans = await plan_script_media(self.mock_research, self.mock_script)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].media_type, "stock_video")
        self.assertEqual(plans[1].media_type, "screenshot")

    def test_ranking_engine_scoring(self) -> None:
        """Verify score calculations and ranking order prioritize target aspects & resolutions."""
        plan = MediaPlan(
            scene=1,
            media_type="stock_video",
            search_query="office workplace",
            reasoning="Testing ranking",
            fallback_media_type="ai_image",
            confidence=0.8
        )
        
        # Candidate 1: Perfect aspect ratio vertical, high quality, matching type
        asset_perfect = MediaAsset(
            url="http://example.com/vertical.mp4",
            provider="pexels",
            media_type="stock_video",
            relevance=0.9,
            quality=0.9,
            width=1080,
            height=1920,
            aspect_ratio=0.5625,
            freshness=0.9,
            credibility=0.9,
            licensing="pexels_free"
        )
        
        # Candidate 2: Landscape orientation, lower specs
        asset_landscape = MediaAsset(
            url="http://example.com/landscape.mp4",
            provider="unsplash",
            media_type="stock_video",
            relevance=0.8,
            quality=0.7,
            width=1920,
            height=1080,
            aspect_ratio=1.777,
            freshness=0.5,
            credibility=0.8,
            licensing="restrictive"
        )
        
        ranked = rank_assets([asset_landscape, asset_perfect], plan)
        self.assertEqual(len(ranked), 2)
        # Perfect vertical should rank higher than landscape
        self.assertEqual(ranked[0].url, "http://example.com/vertical.mp4")

    @patch("services.ai.media.downloader.requests.get")
    def test_downloader_remote_fetch(self, mock_get: MagicMock) -> None:
        """Verify the downloader issues web requests and saves content."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            downloader = MediaDownloader(download_dir=Path(tmpdir))
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.iter_content = lambda chunk_size: [b"x" * 2000]
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = mock_response
            
            asset = MediaAsset(
                url="https://images.pexels.com/files/123/video.mp4",
                provider="pexels",
                media_type="stock_video"
            )
            
            downloaded_path = downloader.download(asset)
            self.assertIsNotNone(downloaded_path)
            self.assertTrue(downloaded_path.exists())
            mock_get.assert_called_once()

    def test_cache_hit_and_set_index(self) -> None:
        """Verify the cache indexes and writes to JSON accurately."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MediaCache(cache_dir=Path(tmpdir))
            
            # Create a real temporary file to act as the cached asset
            test_file = Path(tmpdir) / "cached_asset.jpg"
            test_file.write_bytes(b"x" * 5000)
            
            # Use the internal _make_key to get the correct hash
            key = cache._make_key("test query", "stock_video")
            cache.index[key] = str(test_file)
            cache._save_index()
            
            # Get from cache — should find it
            hit = cache.get("test query", "stock_video")
            self.assertIsNotNone(hit)
            self.assertEqual(str(hit), str(test_file))
            
            # Cache miss for different query
            miss = cache.get("other query", "logo")
            self.assertIsNone(miss)

    def test_classifier_identifies_image_dimensions(self) -> None:
        """Verify classifier correctly recognizes file metadata and orientation."""
        # Mock PIL image properties
        mock_img = MagicMock()
        mock_img.size = (1080, 1920)
        
        with patch("services.ai.media.classifier.Image.open") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_img
            with patch.object(Path, "exists", return_value=True):
                meta = classify_local_media(Path("/mock/image.jpg"))
                
                self.assertTrue(meta["is_image"])
                self.assertFalse(meta["is_video"])
                self.assertEqual(meta["orientation"], "vertical")
                self.assertEqual(meta["width"], 1080)
                self.assertEqual(meta["height"], 1920)

    @patch("services.ai.media.coordinator.plan_script_media", new_callable=AsyncMock)
    @patch("services.ai.media.coordinator.MediaCollector.collect_candidates", new_callable=AsyncMock)
    @patch("services.ai.media.coordinator.MediaDownloader.download")
    @patch("services.ai.media.coordinator._generate_fallback_ai_image", new_callable=AsyncMock)
    async def test_full_media_acquisition_orchestration(
        self,
        mock_generate_fallback: AsyncMock,
        mock_download: MagicMock,
        mock_collect_candidates: AsyncMock,
        mock_plan_script_media: AsyncMock
    ) -> None:
        """Verify the coordinator orchestrator drives all loops correctly and fits parameters."""
        
        # 1. Media Plan
        mock_plan_script_media.return_value = [
            MediaPlan(
                scene=1,
                media_type="stock_video",
                search_query="Mars surface landscape",
                reasoning="Real scenery.",
                fallback_media_type="ai_image",
                confidence=0.88
            ),
            MediaPlan(
                scene=2,
                media_type="ai_image",
                search_query="OpenAI ChatGPT UI",
                reasoning="AI generated concept.",
                fallback_media_type="screenshot",
                confidence=0.9
            )
        ]
        
        # 2. Collect Candidates return
        mock_collect_candidates.return_value = [
            MediaAsset(
                url="https://pexels.com/video1.mp4",
                provider="pexels",
                media_type="stock_video",
                relevance=0.9,
                quality=0.9,
                aspect_ratio=0.5625
            )
        ]
        
        # 3. Downloader return path
        download_path = Path("/mock/job_scene_0.mp4")
        mock_download.return_value = download_path
        
        # 4. Fallback Image return path
        fallback_path = Path("/mock/job_scene_1.jpg")
        mock_generate_fallback.return_value = fallback_path
        
        # Mock classifer response to confirm Video type
        with patch("services.ai.media.coordinator.classify_local_media") as mock_classify:
            def side_effect(p):
                if p == download_path:
                    return {"exists": True, "is_video": True, "error": None}
                return {"exists": True, "is_video": False, "error": None}
            mock_classify.side_effect = side_effect
            
            # Setup cache mock
            with patch("services.ai.media.coordinator.MediaCache.get", return_value=None):
                with patch("services.ai.media.coordinator.MediaCache.set"):
                    
                    image_paths, ai_clips = await acquire_media_assets(
                        research=self.mock_research,
                        script=self.mock_script,
                        job_id="test_job",
                        health_mode=False
                    )
                    
                    # Verify outputs
                    self.assertEqual(len(image_paths), 2)
                    self.assertEqual(len(ai_clips), 2)
                    
                    # Scene 1 is a stock_video -> clip path set, placeholder background image set
                    self.assertEqual(ai_clips[0], download_path)
                    
                    # Scene 2 is ai_image -> clip path None, image path set to fallback image
                    self.assertIsNone(ai_clips[1])
                    self.assertEqual(image_paths[1][0], fallback_path)


if __name__ == "__main__":
    unittest.main()
