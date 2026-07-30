"""
services/ai/media/cache.py — Media Cache

Responsibility:
Prevent duplicate downloads and rate limits by caching acquired media assets 
by their search query and media type.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional
from services.ai.media.visual_intent import AssetKind
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

CACHE_DIR = OUTPUT_DIR / "media_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class MediaCache:
    """
    Caches asset downloads based on the key: hash(query + media_type).
    """
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "cache_index.json"
        self._load_index()

    def _load_index(self):
        """Loads index mapping hashes to local file paths."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    self.index = json.load(f)
            except Exception as e:
                logger.warning("[Cache] Failed to read cache index: %s. Re-initializing.", e)
                self.index = {}
        else:
            self.index = {}

    def _save_index(self):
        """Saves current index state to disk."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error("[Cache] Failed to write cache index: %s", e)

    def _make_key(self, query: str, kind: AssetKind) -> str:
        """Create a reproducible hash key for the query + media type."""
        raw_string = f"{query.strip().lower()}:{kind.value.strip().lower()}"
        return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()

    def get(self, query: str, kind: AssetKind) -> Optional[Path]:
        """
        Retrieves a cached asset path if it exists on disk and in the index.
        """
        key = self._make_key(query, kind)
        cached_path_str = self.index.get(key)
        
        if cached_path_str:
            path = Path(cached_path_str)
            if path.exists() and path.stat().st_size > 100:
                logger.info("[Cache] Cache HIT for query %r, type %r -> %s", query, kind, path.name)
                return path
            else:
                # File was deleted from disk, remove from cache index
                logger.debug("[Cache] Cache record exists but file is missing on disk: %s", cached_path_str)
                self.index.pop(key, None)
                self._save_index()
                
        return None

    def set(self, query: str, kind: AssetKind, local_path: Path) -> None:
        """
        Stores an asset in the cache map.
        Copies the file to the cache directory if not already inside.
        """
        key = self._make_key(query, kind)
        
        # Store in cache directory if not already there, to avoid cleaning deletions
        if not local_path.resolve().is_relative_to(self.cache_dir.resolve()):
            cache_file_path = self.cache_dir / f"cached_{key}{local_path.suffix}"
            try:
                # If target cache file doesn't exist, copy it
                if not cache_file_path.exists():
                    import shutil
                    shutil.copy2(local_path, cache_file_path)
                local_path = cache_file_path
            except Exception as e:
                logger.warning("[Cache] Failed to copy file to cache folder: %s. Storing original path instead.", e)

        self.index[key] = str(local_path)
        self._save_index()
        logger.info("[Cache] Cached query %r, type %r -> %s", query, kind, local_path.name)
