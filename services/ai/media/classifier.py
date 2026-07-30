"""
services/ai/media/classifier.py — Media Classifier

Responsibility:
Inspect downloaded local files to verify their properties (mime type, dimensions,
aspect ratio, and orientation) aligning with expected video specifications.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Dict, Any

from PIL import Image

logger = logging.getLogger(__name__)


def classify_local_media(file_path: Path) -> Dict[str, Any]:
    """
    Inspects a local file and returns metadata including dimensions, mime-type, 
    aspect ratio, orientation, and validity.
    """
    metadata: Dict[str, Any] = {
        "path": str(file_path),
        "exists": file_path.exists(),
        "mime_type": None,
        "width": 0,
        "height": 0,
        "aspect_ratio": 1.0,
        "orientation": "unknown", # vertical | horizontal | square
        "is_image": False,
        "is_video": False,
        "error": None,
    }

    if not file_path.exists():
        metadata["error"] = "File does not exist"
        return metadata

    # 1. Guess mime-type
    mime, _ = mimetypes.guess_type(file_path)
    metadata["mime_type"] = mime
    
    # Simple extension fallback if mimetypes fails
    ext = file_path.suffix.lower()
    
    # 2. Check if image vs video
    if (mime and mime.startswith("image")) or ext in (".png", ".jpg", ".jpeg", ".webp"):
        metadata["is_image"] = True
    elif (mime and mime.startswith("video")) or ext in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
        metadata["is_video"] = True

    # 3. Read image properties
    if metadata["is_image"]:
        try:
            with Image.open(file_path) as img:
                w, h = img.size
                metadata["width"] = w
                metadata["height"] = h
                if h > 0:
                    metadata["aspect_ratio"] = w / h
                
                # Check orientation
                if w == h:
                    metadata["orientation"] = "square"
                elif h > w:
                    metadata["orientation"] = "vertical"
                else:
                    metadata["orientation"] = "horizontal"
                    
        except Exception as exc:
            metadata["error"] = f"Failed to parse image file: {exc}"
            logger.warning("[Classifier] Failed to parse image details for %s: %s", file_path.name, exc)

    # 4. Check video properties (lightweight info)
    elif metadata["is_video"]:
        # Videos can be queried via ffprobe if installed. However, we can treat them
        # as video files and let FFmpeg composition handle scaling and padding natively.
        # Let's set typical defaults or stub for resolution.
        metadata["width"] = 1920
        metadata["height"] = 1080
        metadata["aspect_ratio"] = 16.0 / 9.0
        metadata["orientation"] = "horizontal"
        
        # Check standard properties using a brief subprocess call to ffprobe if available
        import shutil
        if shutil.which("ffprobe"):
            try:
                import json
                import subprocess
                cmd = [
                    "ffprobe", "-v", "error", 
                    "-select_streams", "v:0", 
                    "-show_entries", "stream=width,height", 
                    "-of", "json", str(file_path)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    info = json.loads(res.stdout)
                    stream = info.get("streams", [{}])[0]
                    w = int(stream.get("width", 1920))
                    h = int(stream.get("height", 1080))
                    metadata["width"] = w
                    metadata["height"] = h
                    aspect = w / h if h > 0 else 1.777
                    metadata["aspect_ratio"] = aspect
                    if w == h:
                        metadata["orientation"] = "square"
                    elif h > w:
                        metadata["orientation"] = "vertical"
                    else:
                        metadata["orientation"] = "horizontal"
            except Exception as e:
                logger.debug("[Classifier] ffprobe parse failed: %s", e)

    return metadata
