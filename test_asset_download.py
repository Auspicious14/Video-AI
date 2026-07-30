#!/usr/bin/env python3
"""
Quick test of asset download functionality with mock assets.
Tests the download flow without needing full pipeline run.
"""

import asyncio
import logging
from pathlib import Path

from services.ai.media.downloader import MediaDownloader
from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from config import OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_download_flow():
    """Test asset download with real provider URLs."""
    
    logger.info("=" * 80)
    logger.info("TESTING ASSET DOWNLOAD FUNCTIONALITY")
    logger.info("=" * 80)
    
    downloader = MediaDownloader()
    
    # Test assets from real providers
    test_assets = [
        MediaAsset(
            url="https://images.pexels.com/photos/30608594/pexels-photo-30608594.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
            kind=AssetKind.STOCK_IMAGE,
            provider="pexels",
            provider_id="pexels_30608594",
            title="NVIDIA logo on smartphone",
        ),
        MediaAsset(
            url="https://images.unsplash.com/photo-1591370874773-6702e8f12fd8?w=640",
            kind=AssetKind.STOCK_IMAGE,
            provider="unsplash",
            provider_id="unsplash_test",
            title="Technology image",
        ),
    ]
    
    downloaded = []
    failed = []
    
    for i, asset in enumerate(test_assets):
        logger.info(f"\n[{i+1}/{len(test_assets)}] Downloading {asset.kind.value} from {asset.provider}...")
        logger.info(f"  URL: {asset.url}")
        
        try:
            local_asset = downloader.download(asset)
            
            if local_asset.local_path.exists():
                size_bytes = local_asset.local_path.stat().st_size
                size_mb = size_bytes / 1024 / 1024
                
                logger.info(f"  ✅ SUCCESS")
                logger.info(f"     Path: {local_asset.local_path}")
                logger.info(f"     Size: {size_mb:.2f} MB ({size_bytes:,} bytes)")
                logger.info(f"     MIME: {local_asset.mime_type}")
                
                downloaded.append({
                    "provider": asset.provider,
                    "kind": asset.kind.value,
                    "path": str(local_asset.local_path),
                    "size_bytes": size_bytes,
                })
            else:
                logger.error(f"  ❌ Download succeeded but file not found!")
                failed.append(asset.provider)
                
        except Exception as e:
            logger.error(f"  ❌ FAILED: {e}")
            failed.append(asset.provider)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("DOWNLOAD TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Successfully downloaded: {len(downloaded)}/{len(test_assets)}")
    logger.info(f"Failed: {len(failed)}/{len(test_assets)}")
    
    if downloaded:
        logger.info("\n✅ Downloaded assets:")
        for d in downloaded:
            logger.info(f"  - {d['provider']}/{d['kind']}: {d['size_bytes']:,} bytes")
    
    if failed:
        logger.warning(f"\n⚠️  Failed providers: {', '.join(failed)}")
    
    # Check media directory
    media_dir = OUTPUT_DIR / "media"
    if media_dir.exists():
        all_files = list(media_dir.glob("*"))
        total_size = sum(f.stat().st_size for f in all_files if f.is_file())
        
        logger.info(f"\n📁 Media directory: {media_dir}")
        logger.info(f"   Total files: {len(all_files)}")
        logger.info(f"   Total size: {total_size / 1024 / 1024:.2f} MB")
    
    # Final verdict
    logger.info("\n" + "=" * 80)
    if len(downloaded) == len(test_assets):
        logger.info("🎉 ALL DOWNLOADS SUCCESSFUL!")
        logger.info("✅ Asset download pipeline is working correctly")
    elif len(downloaded) > 0:
        logger.warning("⚠️  PARTIAL SUCCESS")
        logger.warning(f"   {len(downloaded)}/{len(test_assets)} downloads succeeded")
    else:
        logger.error("❌ ALL DOWNLOADS FAILED")
    
    logger.info("=" * 80)
    
    return len(downloaded) == len(test_assets)


if __name__ == "__main__":
    success = asyncio.run(test_download_flow())
    exit(0 if success else 1)
