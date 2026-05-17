from typing import Dict, Optional
from .schema import CharacterIdentityProfile

class CharacterRegistry:
    """
    Responsible for storing and retrieving canonical character profiles.
    Ensures character identity survives across scenes, sequences, and productions.
    """
    
    def __init__(self):
        # In a real system, this would be a persistent database (e.g., PostgreSQL, MongoDB)
        self._profiles: Dict[str, CharacterIdentityProfile] = {}

    def get_profile(self, character_id: str) -> Optional[CharacterIdentityProfile]:
        """Retrieves a character profile by its unique ID."""
        return self._profiles.get(character_id)

    def save_profile(self, profile: CharacterIdentityProfile):
        """Saves or updates a character profile."""
        self._profiles[profile.character_id] = profile

    def list_reusable_actors(self) -> list[CharacterIdentityProfile]:
        """Returns a list of all registered character profiles available for reuse."""
        return list(self._profiles.values())

    def delete_profile(self, character_id: str):
        """Removes a character profile from the registry."""
        if character_id in self._profiles:
            del self._profiles[character_id]

    def update_appearance(self, character_id: str, new_appearance: dict):
        """
        Updates specific appearance traits while maintaining identity continuity.
        Only allowed if the traits are listed as mutable in the profile.
        """
        profile = self.get_profile(character_id)
        if not profile:
            return

        for trait, value in new_appearance.items():
            if trait in profile.continuity_constraints.mutable_traits:
                setattr(profile.appearance_profile, trait, value)
            elif trait in profile.continuity_constraints.immutable_traits:
                # In a real system, this would raise a validation error or log a warning
                pass
        
        self.save_profile(profile)
