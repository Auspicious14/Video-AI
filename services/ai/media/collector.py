"""
services/ai/media/collector.py — Media Collector

Responsibility:
Coordinate pluggable search providers (such as Pexels, Unsplash, Wikimedia Commons, 
Local Assets, and AI fallback) to gather candidate visual assets for each scene plan.
"""

from __future__ import annotations

import os
import logging
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import requests
from pydantic import BaseModel, Field
from services.ai.media.asset_types import AssetKind 

from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.providers.base import MediaProvider
from services.ai.media.visual_intent import VisualIntent

logger = logging.getLogger(__name__)


class MediaAsset(BaseModel):

    url: str

    kind: AssetKind

    provider: str

    provider_id: str

    title: str = ""

    description: str = ""

    tags: list[str] = []

    preview_url: str | None = None

    author: str | None = None

    relevance: float = 0.8

    quality: float = 0.8

    width: int = 0

    height: int = 0

    aspect_ratio: float = 0.56

    freshness: float = 0.8

    credibility: float = 0.8

    licensing: str = "unknown"


class MediaProvider(ABC):
    """
    Abstract Base Class representing a search provider.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    async def search(self, query: str, media_type: str, limit: int = 5) -> List[MediaAsset]:
        pass


# ─── Provider 1: Wikimedia Commons (Public, no API key needed) ─────────────────────

class WikimediaProvider(MediaProvider):
    @property
    def name(self) -> str:
        return "wikimedia_commons"

    def is_configured(self) -> bool:
        return True  # Public API

    async def search(self, query: str, media_type: str, limit: int = 5) -> List[MediaAsset]:
        assets = []
        logger.debug("[WikimediaProvider] Searching for: %s", query)
        
        try:
            # Query Wikimedia Commons search API for files (namespace 6)
            encoded_query = urllib.parse.quote(query)
            search_url = (
                "https://commons.wikimedia.org/w/api.php?"
                "action=query&list=search&srsearch={}&srnamespace=6&format=json&origin=*"
            ).format(encoded_query)

            resp = requests.get(search_url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            search_results = data.get("query", {}).get("search", [])
            for item in search_results[:limit]:
                title = item.get("title")
                if not title:
                    continue

                # Fetch details for the file title
                encoded_title = urllib.parse.quote(title)
                info_url = (
                    "https://commons.wikimedia.org/w/api.php?"
                    "action=query&titles={}&prop=imageinfo&iiprop=url|size|mime&format=json&origin=*"
                ).format(encoded_title)

                info_resp = requests.get(info_url, timeout=10)
                info_resp.raise_for_status()
                info_data = info_resp.json()

                pages = info_data.get("query", {}).get("pages", {})
                for page_id, page_info in pages.items():
                    image_info_list = page_info.get("imageinfo", [])
                    if not image_info_list:
                        continue

                    img_info = image_info_list[0]
                    file_url = img_info.get("url")
                    mime = img_info.get("mime", "")
                    
                    if not file_url:
                        continue

                    # Filter out unsupported file types
                    if "image/gif" in mime or "svg" in file_url:
                        continue

                    w = img_info.get("width", 1080)
                    h = img_info.get("height", 1920)
                    aspect = w / h if h > 0 else 0.5625

                    # Map properties
                    credibility = 0.9  # Academic/Wikimedia sources are highly credible
                    licensing = "public_domain" if "pd" in title.lower() else "creative_commons"

                    assets.append(
                        MediaAsset(
                            url=file_url,
                            provider=self.name,
                            media_type=media_type,
                            relevance=0.85,
                            quality=0.75,
                            width=w,
                            height=h,
                            aspect_ratio=aspect,
                            freshness=0.6,  # Archive photos are older
                            credibility=credibility,
                            licensing=licensing,
                        )
                    )

        except Exception as exc:
            logger.warning("[WikimediaProvider] Search request failed: %s", exc)

        return assets


# ─── Provider 2: Pexels API (Requires key) ──────────────────────────────────────────

class PexelsProvider(MediaProvider):
    @property
    def name(self) -> str:
        return "pexels"

    def is_configured(self) -> bool:
        return bool(os.getenv("PEXELS_API_KEY"))

    async def search(self, query: str, media_type: str, limit: int = 5) -> List[MediaAsset]:
        token = os.getenv("PEXELS_API_KEY")
        if not token:
            return []

        assets = []
        logger.debug("[PexelsProvider] Searching for: %s", query)
        headers = {"Authorization": token}
        
        # Pexels supports both videos and photos
        is_video = media_type == "stock_video"
        endpoint = "videos/search" if is_video else "search"
        url = f"https://api.pexels.com/{is_video}/v1/{endpoint}?query={urllib.parse.quote(query)}&per_page={limit}"

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("videos" if is_video else "photos", [])
            for item in items:
                w = item.get("width", 1080)
                h = item.get("height", 1920)
                aspect = w / h if h > 0 else 0.5625

                if is_video:
                    video_files = item.get("video_files", [])
                    # Prefer HD/vertical mp4 file
                    selected_file = None
                    for vf in video_files:
                        if vf.get("file_type") == "video/mp4":
                            selected_file = vf.get("link")
                            w = vf.get("width", w)
                            h = vf.get("height", h)
                            aspect = w / h if h > 0 else 0.5625
                            break
                    if not selected_file and video_files:
                        selected_file = video_files[0].get("link")
                    
                    file_url = selected_file
                else:
                    file_url = item.get("src", {}).get("large2x")

                if not file_url:
                    continue

                assets.append(
                    MediaAsset(
                        url=file_url,
                        provider=self.name,
                        media_type=media_type,
                        relevance=0.9,
                        quality=0.85,
                        width=w,
                        height=h,
                        aspect_ratio=aspect,
                        freshness=0.9,
                        credibility=0.85,
                        licensing="pexels_free",
                    )
                )

        except Exception as exc:
            logger.warning("[PexelsProvider] Search request failed: %s", exc)

        return assets


# ─── Provider 3: Unsplash API (Requires key) ────────────────────────────────────────

class UnsplashProvider(MediaProvider):
    @property
    def name(self) -> str:
        return "unsplash"

    def is_configured(self) -> bool:
        return bool(os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("UNSPLASH_API_KEY"))

    async def search(self, query: str, media_type: str, limit: int = 5) -> List[MediaAsset]:
        token = os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("UNSPLASH_API_KEY")
        if not token:
            return []

        assets = []
        logger.debug("[UnsplashProvider] Searching for: %s", query)
        headers = {"Authorization": f"Client-ID {token}"}
        url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&per_page={limit}"

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            for item in results:
                file_url = item.get("urls", {}).get("regular")
                if not file_url:
                    continue

                w = item.get("width", 1080)
                h = item.get("height", 1920)
                aspect = w / h if h > 0 else 0.5625

                assets.append(
                    MediaAsset(
                        url=file_url,
                        provider=self.name,
                        media_type=media_type,
                        relevance=0.9,
                        quality=0.9,
                        width=w,
                        height=h,
                        aspect_ratio=aspect,
                        freshness=0.9,
                        credibility=0.9,
                        licensing="unsplash_free",
                    )
                )

        except Exception as exc:
            logger.warning("[UnsplashProvider] Search request failed: %s", exc)

        return assets


# ─── Provider 4: Simulated Local asset generator (for test suite stability) ───────

class SimulationProvider(MediaProvider):
    @property
    def name(self) -> str:
        return "simulated_local"

    def is_configured(self) -> bool:
        return True  # Always fallback enabled for dev/test ease

    async def search(self, query: str, media_type: str, limit: int = 5) -> List[MediaAsset]:
        # Returns high-quality mock urls representing requested visual.
        # This keeps rendering tests stable even with no internet / poor API limits.
        logger.debug("[SimulationProvider] Generating simulated asset for query: %s", query)
        
        # Use standard high-quality royalty-free image URLs for placeholder
        # Based on media types, give appropriate unsplash links that are guaranteed to load.
        placeholders = {
            "screenshot": "https://images.unsplash.com/photo-1531403009284-440f080d1e12?w=1080&h=1920&fit=crop", # UI/UX
            "logo": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1080&h=1920&fit=crop", # Vector design
            "website": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1080&h=1920&fit=crop", # Code/Dashboard
            "product_image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=1080&h=1920&fit=crop", # Gadget
            "stock_video": "https://images.unsplash.com/photo-1473116763269-255ea74275af?w=1080&h=1920&fit=crop", # Nature/Scenic
            "historical_photo": "https://images.unsplash.com/photo-1543857778-c4a1a3e0b2eb?w=1080&h=1920&fit=crop", # Old book/library
            "chart": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=1080&h=1920&fit=crop", # Graph/Presentation
            "map": "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=1080&h=1920&fit=crop", # Earth map
            "ai_image": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=1080&h=1920&fit=crop" # AI Art
        }
        
        url = placeholders.get(media_type, placeholders["ai_image"])
        # We append direct query to help identify it in download logs
        url += f"&q_tag={urllib.parse.quote(query[:30])}"

        return [
            MediaAsset(
                url=url,
                provider=self.name,
                media_type=media_type,
                relevance=0.92,
                quality=0.88,
                width=1080,
                height=1920,
                aspect_ratio=0.5625,
                freshness=0.95,
                credibility=0.8,
                licensing="CC0_simulation",
            )
        ]


# ─── Media Acquisition Collector Coordinator ──────────────────────────────────────

class MediaCollector:
    """
    Main registry which gathers candidates from all configured Search Providers.
    """
    def __init__(self):
        self.providers: List[MediaProvider] = [
            WikimediaProvider(),
            PexelsProvider(),
            UnsplashProvider(),
            SimulationProvider()
        ]

    def register_provider(self, provider: MediaProvider):
        """Allows runtime dynamic registration of new search libraries."""
        # Ensure we add before SimulationProvider (so local fallback stays last)
        self.providers.insert(-1, provider)
        logger.info("Registered media provider: %s", provider.name)

    async def collect_candidates(self, query: str, media_type: str, limit: int = 5) -> List[MediaAsset]:
        """
        Queries all configured and active search libraries to return a pool of asset options.
        """
        all_candidates: List[MediaAsset] = []
        
        for provider in self.providers:
            if provider.is_configured():
                try:
                    results = await provider.search(query, media_type, limit=limit)
                    if results:
                        logger.debug("Provider %s returned %d candidates for: %r", provider.name, len(results), query)
                        all_candidates.extend(results)
                except Exception as exc:
                    logger.error("Error collecting assets from %s: %s", provider.name, exc)
                    
        return all_candidates
