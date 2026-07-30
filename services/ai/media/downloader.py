# """
# services/ai/media/downloader.py — Media Downloader

# Responsibility:
# Fetch/download selected remote visual assets (images or videos) to the local disk,
# or copy/resolve local file paths.
# """

# from __future__ import annotations

# import logging
# import os
# import shutil
# from pathlib import Path
# import requests

# from services.ai.media.collector import MediaAsset
# from config import OUTPUT_DIR

# logger = logging.getLogger(__name__)

# DOWNLOAD_DIR = OUTPUT_DIR / "media_downloads"
# DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# class MediaDownloader:
#     """
#     Handles fetching of remote assets and saving them locally.
#     """
#     def __init__(self, download_dir: Path = DOWNLOAD_DIR):
#         self.download_dir = download_dir
#         self.download_dir.mkdir(parents=True, exist_ok=True)

#     def download(self, asset: MediaAsset, filename_prefix: str = "media") -> Path:
#         """
#         Downloads the asset to the configured directory and returns its local Path.
#         If the asset URL is already a local path, it is returned directly.
#         """
#         url = asset.url
#         logger.debug("[Downloader] Request to download url: %s", url)

#         # 1. Resolve local files directly
#         if url.startswith("/") or url.startswith("file://") or os.path.exists(url):
#             clean_path = url.replace("file://", "")
#             local_p = Path(clean_path)
#             if local_p.exists():
#                 logger.info("[Downloader] Asset is already local: %s", local_p)
#                 return local_p

#         # 2. Extract or guess extension
#         # We can extract extension from URL, defaulting to .jpg or .mp4
#         parsed_url = url.split("?")[0]
#         ext = Path(parsed_url).suffix.lower()
#         if not ext:
#             # Guess based on media type
#             ext = ".mp4" if asset.media_type.lower() == "stock_video" else ".jpg"

#         # Special casing Unsplash / Pixazo without direct extensions
#         if "unsplash.com" in url and not ext:
#             ext = ".jpg"

#         # Unique name based on URL hash to prevent duplicates
#         url_hash = str(hash(url) & 0xffffffff)
#         local_filename = f"{filename_prefix}_{url_hash}{ext}"
#         local_path = self.download_dir / local_filename

#         # If already downloaded, return it
#         if local_path.exists() and local_path.stat().st_size > 1000:
#             logger.info("[Downloader] Target already downloaded: %s", local_path)
#             return local_path

#         # 3. Perform network download
#         logger.info("[Downloader] Starting network download of %s from %s...", asset.media_type, asset.provider)
#         try:
#             headers = {
#                 "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 VideoAI/2.0"
#             }
#             # Handle standard network requests
#             response = requests.get(url, headers=headers, stream=True, timeout=30)
#             response.raise_for_status()

#             with open(local_path, "wb") as f:
#                 for chunk in response.iter_content(chunk_size=8192):
#                     if chunk:
#                         f.write(chunk)

#             logger.info("[Downloader] ✓ Downloaded successfully: %s (%d bytes)", local_path.name, local_path.stat().st_size)
#             return local_path

#         except Exception as exc:
#             logger.error("[Downloader] Failed to download asset from %s: %s", url, exc)
#             # Clean up partial files
#             if local_path.exists():
#                 local_path.unlink()
#             raise RuntimeError(f"Failed to download asset: {exc}") from exc


from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path

import requests

from config import OUTPUT_DIR
from services.ai.media.asset import MediaAsset
from services.ai.media.local_asset import LocalAsset


logger = logging.getLogger(__name__)

DOWNLOAD_DIR = OUTPUT_DIR / "media"

DOWNLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


class MediaDownloader:

    def __init__(
        self,
        download_dir: Path = DOWNLOAD_DIR,
    ):

        self.download_dir = download_dir

    def download(
        self,
        asset: MediaAsset,
    ) -> LocalAsset:
        """
        Download a MediaAsset and return a LocalAsset with the local file path.
        
        Args:
            asset: MediaAsset to download
            
        Returns:
            LocalAsset with populated local_path and all required fields
            
        Raises:
            RuntimeError: If download fails after retries
        """
        url = asset.url
        
        # Handle already-local files
        if url.startswith("file://"):
            url = url.replace("file://", "")
        
        if Path(url).is_absolute() and Path(url).exists():
            logger.info(f"[Downloader] Asset already local: {url}")
            local_path = Path(url)
            return LocalAsset(
                source_provider=asset.provider,
                provider_id=asset.provider_id,
                local_path=local_path,
                kind=asset.kind,
                width=asset.width or 1920,
                height=asset.height or 1080,
                duration=getattr(asset, 'duration', None),
                fps=getattr(asset, 'fps', None),
                filesize=local_path.stat().st_size,
                mime_type=self._mime(local_path),
                checksum=self._checksum(local_path),
                score=asset.score or 0.0,
                metadata={},
            )
        
        # Generate filename from URL
        # Use hash to avoid collisions and filesystem issues
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        
        # Determine extension from URL or asset kind
        parsed_url = url.split("?")[0]  # Remove query params
        ext = Path(parsed_url).suffix.lower()
        
        if not ext:
            # Guess from asset kind
            from services.ai.media.asset_types import AssetKind
            if asset.kind == AssetKind.STOCK_VIDEO:
                ext = ".mp4"
            elif asset.kind in {AssetKind.STOCK_IMAGE, AssetKind.AI_IMAGE}:
                ext = ".jpg"
            else:
                ext = ".dat"
        
        # Build destination path
        filename = f"{asset.provider}_{url_hash}{ext}"
        destination = self.download_dir / filename
        
        # Return cached if exists
        if destination.exists() and destination.stat().st_size > 1000:
            logger.info(f"[Downloader] Using cached download: {destination.name}")
            return LocalAsset(
                source_provider=asset.provider,
                provider_id=asset.provider_id,
                local_path=destination,
                kind=asset.kind,
                width=asset.width or 1920,
                height=asset.height or 1080,
                duration=getattr(asset, 'duration', None),
                fps=getattr(asset, 'fps', None),
                filesize=destination.stat().st_size,
                mime_type=self._mime(destination),
                checksum=self._checksum(destination),
                score=asset.score or 0.0,
                metadata={},
            )
        
        # Download with retries
        logger.info(f"[Downloader] Downloading {asset.kind.value} from {asset.provider}: {url}")
        try:
            self._download_with_retry(url, destination, retries=3)
            
            # Verify download
            if not destination.exists():
                raise RuntimeError(f"Download completed but file not found: {destination}")
            
            if destination.stat().st_size < 1000:
                raise RuntimeError(f"Downloaded file too small ({destination.stat().st_size} bytes), likely failed")
            
            logger.info(f"[Downloader] ✓ Downloaded {destination.name} ({destination.stat().st_size:,} bytes)")
            
            return LocalAsset(
                source_provider=asset.provider,
                provider_id=asset.provider_id,
                local_path=destination,
                kind=asset.kind,
                width=asset.width or 1920,
                height=asset.height or 1080,
                duration=getattr(asset, 'duration', None),
                fps=getattr(asset, 'fps', None),
                filesize=destination.stat().st_size,
                mime_type=self._mime(destination),
                checksum=self._checksum(destination),
                score=asset.score or 0.0,
                metadata={},
            )
            
        except Exception as e:
            # Clean up partial downloads
            if destination.exists():
                destination.unlink()
            logger.error(f"[Downloader] Failed to download from {asset.provider}: {e}")
            raise RuntimeError(f"Download failed: {e}") from e

    def _download_file(
    self,
    url: str,
    destination: Path):

        headers = {
            "User-Agent": "VideoAI/3.0"
        }

        response = requests.get(
            url,
            stream=True,
            headers=headers,
            timeout=60,
        )

        response.raise_for_status()

        with destination.open("wb") as file:

            for chunk in response.iter_content(8192):

                if chunk:

                    file.write(chunk)
    
    def _checksum(
    self,
    path: Path,
) -> str:

        digest = hashlib.sha256()

        with path.open("rb") as f:

            while True:

                chunk = f.read(8192)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    def _mime(
    self,
    path: Path,
):

        mime, _ = mimetypes.guess_type(path)

        return mime or "application/octet-stream"
    
    def _download_with_retry(
    self,
    url: str,
    destination: Path,
    retries: int = 3,
):

        last_error = None

        for _ in range(retries):

            try:

                self._download_file(
                    url,
                    destination,
                )

                return

            except Exception as e:

                last_error = e

                logger.warning(e)

        raise RuntimeError(last_error)


