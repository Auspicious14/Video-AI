"""Small JSON artifact cache for production stages."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

STUDIO_CACHE_DIR = Path(os.getenv("OUTPUT_DIR", "outputs")) / "studio_cache"
STUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
STUDIO_CACHE_VERSION = os.getenv("STUDIO_CACHE_VERSION", "1")

def cache_key(stage: str, payload: dict) -> str:
    raw = json.dumps({"v": STUDIO_CACHE_VERSION, **payload}, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{stage}_{digest}"


def artifact_path(key: str) -> Path:
    return STUDIO_CACHE_DIR / f"{key}.json"


async def get_or_create_artifact(
    *,
    stage: str,
    payload: dict,
    model: type[T],
    factory: Callable[[], object],
) -> T:
    """
    Load a validated artifact from cache or run the async factory and persist it.

    The cache is intentionally plain JSON so creators and future admin tools can
    inspect or edit stage output without needing provider logs.
    """
    key = cache_key(stage, payload)
    path = artifact_path(key)
    if path.exists():
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    result = await factory()
    artifact = model.model_validate(result)
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    return artifact
