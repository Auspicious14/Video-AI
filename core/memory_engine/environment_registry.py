from typing import Dict, Optional
from .schema import EnvironmentIdentityProfile

class EnvironmentRegistry:
    """
    Responsible for environment persistence and location continuity.
    Ensures that locations remain geographically, visually, and atmospherically stable.
    """
    
    def __init__(self):
        # In a real system, this would be a persistent database
        self._profiles: Dict[str, EnvironmentIdentityProfile] = {}

    def get_profile(self, environment_id: str) -> Optional[EnvironmentIdentityProfile]:
        """Retrieves an environment profile by its unique ID."""
        return self._profiles.get(environment_id)

    def save_profile(self, profile: EnvironmentIdentityProfile):
        """Saves or updates an environment profile."""
        self._profiles[profile.environment_id] = profile

    def list_reusable_worlds(self) -> list[EnvironmentIdentityProfile]:
        """Returns a list of all registered environment profiles available for reuse."""
        return list(self._profiles.values())

    def update_lighting(self, environment_id: str, new_lighting_style: str):
        """
        Updates the lighting style of an environment.
        Only allowed if lighting is not locked as an immutable element.
        """
        profile = self.get_profile(environment_id)
        if not profile:
            return

        if "lighting" not in profile.continuity_constraints.immutable_elements:
            profile.visual_profile.lighting_style = new_lighting_style
            self.save_profile(profile)
