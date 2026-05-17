from typing import List, Dict, Optional
from .schema import MemoryTimeline, MemoryEvent, EmotionalShift, ContinuityEvent

class ContinuityMemoryManager:
    """
    Tracks long-term continuity memory across stories and scenes.
    Maintains memory timelines, locks continuity-critical facts, and tracks emotional residue.
    """
    
    def __init__(self):
        # story_id -> MemoryTimeline
        self._timelines: Dict[str, MemoryTimeline] = {}

    def get_timeline(self, story_id: str) -> MemoryTimeline:
        """Retrieves or initializes a memory timeline for a story."""
        if story_id not in self._timelines:
            self._timelines[story_id] = MemoryTimeline(story_id=story_id)
        return self._timelines[story_id]

    def record_character_event(self, story_id: str, character_id: str, event: MemoryEvent):
        """Records a memory event for a specific character."""
        timeline = self.get_timeline(story_id)
        if character_id not in timeline.character_history:
            timeline.character_history[character_id] = []
        timeline.character_history[character_id].append(event)

    def record_environment_event(self, story_id: str, environment_id: str, event: MemoryEvent):
        """Records a memory event for a specific environment."""
        timeline = self.get_timeline(story_id)
        if environment_id not in timeline.environment_history:
            timeline.environment_history[environment_id] = []
        timeline.environment_history[environment_id].append(event)

    def record_emotional_shift(self, story_id: str, shift: EmotionalShift):
        """Records an emotional shift for a character in the timeline."""
        timeline = self.get_timeline(story_id)
        timeline.emotional_history.append(shift)

    def lock_continuity_fact(self, story_id: str, event: ContinuityEvent):
        """Locks a continuity-critical fact (e.g., character received a scar, lighting changed)."""
        timeline = self.get_timeline(story_id)
        timeline.continuity_events.append(event)

    def get_emotional_residue(self, story_id: str, character_id: str) -> Optional[str]:
        """
        Retrieves the 'emotional residue' for a character based on their history.
        Useful for ensuring behavioral consistency and gradual evolution.
        """
        timeline = self.get_timeline(story_id)
        relevant_shifts = [s for s in timeline.emotional_history if s.character_id == character_id]
        if not relevant_shifts:
            return None
        
        # Simple logic: the last recorded emotion is the residue
        return relevant_shifts[-1].to_emotion

    def get_active_continuity_locks(self, story_id: str) -> List[ContinuityEvent]:
        """Returns all active continuity locks for a given story."""
        timeline = self.get_timeline(story_id)
        return timeline.continuity_events
