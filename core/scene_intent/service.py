from core.cinematic_state.models import CinematicStateGraph
from .schema import SceneIntent, EnvironmentDirection, ContinuityUpdates
from .planner import ScenePlanner
from .camera_mapper import CameraMapper
from .character_director import CharacterDirector

class SceneIntentService:
    def __init__(self):
        self.planner = ScenePlanner()
        self.camera_mapper = CameraMapper()
        self.character_director = CharacterDirector()

    def generate_scene_intent(self, state: CinematicStateGraph) -> SceneIntent:
        """
        Orchestrates the full pipeline to convert CinematicStateGraph -> SceneIntent.
        """
        # 1. & 2. Data already extracted from 'state'
        
        # 3. Determine narrative_purpose
        purpose = self.planner.determine_narrative_purpose(state)
        
        # 4. Compute emotional_target shift
        emotional_target = self.planner.determine_emotional_target(state)
        
        # 5. Generate character_directions
        character_directions = self.character_director.generate_directions(state, emotional_target)
        
        # 6. Generate scene_beats
        scene_beats = self.planner.generate_scene_beats(state, purpose, emotional_target)
        
        # 7. Map camera_direction
        camera_direction = self.camera_mapper.map_emotion_to_camera(emotional_target)
        
        # 8. Generate dialogue_intent
        dialogue_intent = self.character_director.generate_dialogue_intent(state, emotional_target)
        
        # 9. Produce continuity_updates
        # This is a placeholder for more complex logic that would derive facts from state/history
        continuity_updates = ContinuityUpdates(
            new_facts=[f"Scene focus: {purpose}"],
            resolved_facts=[]
        )
        
        # 10. Return SceneIntent
        return SceneIntent(
            story_id=state.story_id,
            scene_id=f"scene_{state.narrative_state.current_scene_index}",
            sequence_id=state.narrative_state.current_sequence,
            narrative_purpose=purpose,
            emotional_target=emotional_target,
            tension_delta=self.planner.determine_tension_delta(state),
            character_directions=character_directions,
            scene_beats=scene_beats,
            environment_direction=EnvironmentDirection(
                location=state.environment.location,
                time_of_day=state.environment.time_of_day,
                audio_atmosphere=state.environment.audio_atmosphere
            ),
            camera_direction=camera_direction,
            dialogue_intent=dialogue_intent,
            continuity_updates=continuity_updates
        )

# Singleton instance
service = SceneIntentService()

def generate_scene_intent(state: CinematicStateGraph) -> SceneIntent:
    return service.generate_scene_intent(state)
