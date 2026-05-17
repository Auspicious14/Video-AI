import json
import os
from pathlib import Path
from typing import Optional
from .models import CinematicStateGraph

DATA_DIR = Path("data/cinematic_states")
DATA_DIR.mkdir(parents=True, exist_ok=True)

class FileStorage:
    def __init__(self, base_dir: Path = DATA_DIR):
        self.base_dir = base_dir

    def _get_path(self, story_id: str) -> Path:
        return self.base_dir / f"{story_id}.json"

    def save(self, state: CinematicStateGraph):
        path = self._get_path(state.story_id)
        with open(path, "w") as f:
            f.write(state.model_dump_json(indent=2))

    def load(self, story_id: str) -> Optional[CinematicStateGraph]:
        path = self._get_path(story_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
            return CinematicStateGraph.model_validate(data)

# Singleton instance for the service to use
storage = FileStorage()
