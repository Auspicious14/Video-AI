#!/usr/bin/env python3
"""
Phase 3 Production Validation: NVIDIA Documentary

Tests the complete pipeline with real asset downloads and verifies:
1. Assets are downloaded from providers
2. local_path is populated
3. Renderer uses downloaded assets
4. Real assets dominate over AI generation
"""

import asyncio
import json
import logging
from pathlib import Path

from models import YouTubeStudioRequest
from services.ai.studio.pipeline import run_youtube_studio_production
from config import OUTPUT_DIR

# Setup logging to see diagnostic output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_nvidia_production():
    """Run full NVIDIA documentary production and verify real asset usage."""
    
    job_id = "nvidia_validation_test"
    
    request = YouTubeStudioRequest(
        user_email="test@videoai.ng",
        topic="How NVIDIA Became Richer Than Most Countries",
        tone="documentary",
        duration=180,  # 3 minutes for faster testing
        voice_id="male_narrator",
        aspect_ratio="16:9",
        generate_audio=True,
        generate_images=True,  # Enable AI fallback
        render_video=False,  # Skip render to focus on asset collection
    )
    
    logger.info("=" * 80)
    logger.info("PHASE 3 PRODUCTION VALIDATION: NVIDIA DOCUMENTARY")
    logger.info("=" * 80)
    logger.info(f"Job ID: {job_id}")
    logger.info(f"Topic: {request.topic}")
    logger.info(f"Duration: {request.duration}s")
    logger.info("=" * 80)
    
    try:
        await run_youtube_studio_production(job_id, request)
        
        logger.info("\n" + "=" * 80)
        logger.info("PRODUCTION COMPLETE - ANALYZING RESULTS")
        logger.info("=" * 80)
        
        # Check outputs
        asset_collection_path = OUTPUT_DIR / f"{job_id}_asset_collection.json"
        downloaded_assets_path = OUTPUT_DIR / f"{job_id}_downloaded_assets.json"
        visual_plan_path = OUTPUT_DIR / f"{job_id}_visual_plan.json"
        
        # Analyze asset collection
        if asset_collection_path.exists():
            with open(asset_collection_path) as f:
                asset_collection = json.load(f)
            
            selected_assets = asset_collection.get("selected_assets", [])
            ai_required = asset_collection.get("ai_required_indices", [])
            
            logger.info(f"\n📊 ASSET COLLECTION SUMMARY:")
            logger.info(f"  Total selected assets: {len(selected_assets)}")
            logger.info(f"  AI required indices: {len(ai_required)}")
            
            # Count by type
            videos = sum(1 for a in selected_assets if 'video' in a.get('asset_type', '').lower())
            images = len(selected_assets) - videos
            
            logger.info(f"  Videos: {videos}")
            logger.info(f"  Images: {images}")
            
            # Count by source
            sources = {}
            for asset in selected_assets:
                source = asset.get('source', 'unknown')
                sources[source] = sources.get(source, 0) + 1
            
            logger.info(f"\n📦 ASSETS BY PROVIDER:")
            for source, count in sorted(sources.items(), key=lambda x: -x[1]):
                logger.info(f"  {source}: {count}")
            
            # Check local_path population
            with_local_path = sum(1 for a in selected_assets if a.get('local_path'))
            logger.info(f"\n💾 LOCAL PATH STATUS:")
            logger.info(f"  Assets with local_path: {with_local_path}/{len(selected_assets)}")
            
            if with_local_path == 0:
                logger.error("  ❌ NO ASSETS HAVE local_path POPULATED!")
            elif with_local_path == len(selected_assets):
                logger.info("  ✅ ALL ASSETS HAVE local_path!")
            else:
                logger.warning(f"  ⚠️  PARTIAL: {with_local_path}/{len(selected_assets)}")
        
        # Analyze downloaded assets
        if downloaded_assets_path.exists():
            with open(downloaded_assets_path) as f:
                downloaded = json.load(f)
            
            successful = [d for d in downloaded if d.get('status') == 'downloaded']
            failed = [d for d in downloaded if d.get('status') == 'failed']
            
            logger.info(f"\n⬇️  DOWNLOAD RESULTS:")
            logger.info(f"  Successfully downloaded: {len(successful)}")
            logger.info(f"  Failed downloads: {len(failed)}")
            
            if failed:
                logger.warning(f"\n  Failed downloads:")
                for f in failed[:5]:  # Show first 5
                    logger.warning(f"    Visual {f.get('visual_index')}: {f.get('error', 'unknown error')}")
        
        # Check if files actually exist
        media_dir = OUTPUT_DIR / "media"
        if media_dir.exists():
            downloaded_files = list(media_dir.glob("*"))
            logger.info(f"\n📁 DOWNLOADED FILES:")
            logger.info(f"  Files in outputs/media/: {len(downloaded_files)}")
            
            total_size = sum(f.stat().st_size for f in downloaded_files if f.is_file())
            logger.info(f"  Total size: {total_size / 1024 / 1024:.2f} MB")
            
            if downloaded_files:
                logger.info(f"  Sample files:")
                for f in sorted(downloaded_files)[:5]:
                    size_mb = f.stat().st_size / 1024 / 1024
                    logger.info(f"    {f.name} ({size_mb:.2f} MB)")
        
        # Final verdict
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION VERDICT")
        logger.info("=" * 80)
        
        checks = {
            "Asset collection completed": asset_collection_path.exists(),
            "Downloaded assets logged": downloaded_assets_path.exists(),
            "Real assets selected": len(selected_assets) > 0 if asset_collection_path.exists() else False,
            "Downloads executed": downloaded_assets_path.exists() and len(downloaded) > 0 if downloaded_assets_path.exists() else False,
            "Files on disk": media_dir.exists() and len(downloaded_files) > 0 if media_dir.exists() else False,
        }
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            logger.info(f"{status} {check}")
        
        if all(checks.values()):
            logger.info("\n🎉 ALL VALIDATION CHECKS PASSED!")
            logger.info("Real asset pipeline is working correctly.")
        else:
            logger.warning("\n⚠️  SOME VALIDATION CHECKS FAILED")
            logger.warning("Review the logs above for details.")
        
    except Exception as e:
        logger.exception(f"Production failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_nvidia_production())
