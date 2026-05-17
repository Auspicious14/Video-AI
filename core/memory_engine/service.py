from typing import List, Dict, Any, Optional
from .schema import (
    CharacterIdentityProfile, 
    EnvironmentIdentityProfile, 
    MemoryTimeline, 
    MemoryEvent, 
    EmotionalShift, 
    ContinuityEvent
)
from .character_registry import CharacterRegistry
from .environment_registry import EnvironmentRegistry
from .continuity_memory_manager import ContinuityMemoryManager
from .identity_validator import IdentityValidator
from .asset_reference_manager import AssetReferenceManager

class MemoryEngineService:
    """
    Main entry point for Phase 6: Character Identity + World Memory Engine.
    Orchestrates memory operations, manages persistent continuity, and exposes reusable APIs.
    """
    
    def __init__(self):
        self.character_registry = CharacterRegistry()
        self.environment_registry = EnvironmentRegistry()
        self.continuity_manager = ContinuityMemoryManager()
        self.validator = IdentityValidator()
        self.asset_manager = AssetReferenceManager()

    def get_character_profile(self, character_id: str) -> Optional[CharacterIdentityProfile]:
        """Retrieves a canonical character profile."""
        return self.character_registry.get_profile(character_id)

    def get_environment_profile(self, environment_id: str) -> Optional[EnvironmentIdentityProfile]:
        """Retrieves a canonical environment profile."""
        return self.environment_registry.get_profile(environment_id)

    def update_memory_timeline(self, story_id: str, event_data: Dict[str, Any]):
        """
        Updates the memory timeline for a story.
        Can handle character events, environment events, emotional shifts, and continuity locks.
        """
        if "character_id" in event_data:
            event = MemoryEvent(**event_data)
            self.continuity_manager.record_character_event(story_id, event_data["character_id"], event)
        
        if "environment_id" in event_data:
            event = MemoryEvent(**event_data)
            self.continuity_manager.record_environment_event(story_id, event_data["environment_id"], event)

        if "shift" in event_data:
            shift = EmotionalShift(**event_data["shift"])
            self.continuity_manager.record_emotional_shift(story_id, shift)

        if "lock" in event_data:
            lock = ContinuityEvent(**event_data["lock"])
            self.continuity_manager.lock_continuity_fact(story_id, lock)

    def validate_identity_consistency(
        self, 
        story_id: str, 
        current_scene_state: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Validates the current scene state against canonical profiles and continuity locks.
        Returns a dictionary of issues found.
        """
        all_issues = {
            "characters": [],
            "environments": []
        }
        
        active_locks = self.continuity_manager.get_active_continuity_locks(story_id)

        # Validate characters in scene
        for char_id, char_state in current_scene_state.get("characters", {}).items():
            profile = self.get_character_profile(char_id)
            if profile:
                issues = self.validator.validate_character_consistency(profile, char_state, active_locks)
                all_issues["characters"].extend(issues)

        # Validate environments in scene
        for env_id, env_state in current_scene_state.get("environments", {}).items():
            profile = self.get_environment_profile(env_id)
            if profile:
                issues = self.validator.validate_environment_consistency(profile, env_state, active_locks)
                all_issues["environments"].extend(issues)

        return all_issues

    def get_validated_memory_context(self, story_id: str, character_ids: List[str], environment_id: str) -> Dict[str, Any]:
        """
        Retrieves a complete memory context for a scene, including profiles and active continuity locks.
        Ensures the storytelling engine has all necessary information to maintain continuity.
        """
        context = {
            "story_id": story_id,
            "characters": {},
            "environment": None,
            "active_locks": self.continuity_manager.get_active_continuity_locks(story_id),
            "emotional_residues": {}
        }

        for char_id in character_ids:
            profile = self.get_character_profile(char_id)
            if profile:
                context["characters"][char_id] = profile
                context["emotional_residues"][char_id] = self.continuity_manager.get_emotional_residue(story_id, char_id)

        env_profile = self.get_environment_profile(environment_id)
        if env_profile:
            context["environment"] = env_profile

        return context
