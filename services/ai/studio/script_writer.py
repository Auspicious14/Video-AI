"""Stage 4: documentary script writer specialist."""

from __future__ import annotations

# Forward all imports from the new separated architecture
from services.ai.studio.script_writer_v2 import (
    run_documentary_script_writer_agent,
    run_metadata_extractor_agent,
    run_narration_writer_agent,
    run_section_based_narration_writer,
)

__all__ = [
    "run_documentary_script_writer_agent",
    "run_narration_writer_agent",
    "run_metadata_extractor_agent",
    "run_section_based_narration_writer",
]
