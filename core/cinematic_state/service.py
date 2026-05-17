from typing import Optional
from .models import (
    CinematicStateGraph, NarrativeState, EnvironmentState, 
    EmotionState, ContinuityMemory, RenderState, SceneResult
)
from .storage import storage

class CinematicStateService:
    @staticmethod
    def create_state(story_id: str) -> CinematicStateGraph:
        """Initializes default CinematicStateGraph and persists it."""
        state = CinematicStateGraph(
            story_id=story_id,
            narrative_state=NarrativeState(
                current_sequence="intro",
                current_scene_index=0,
                tension=0.1
            ),
            environment=EnvironmentState(
                location="unknown",
                time_of_day="day",
                audio_atmosphere="neutral"
            ),
            emotion_state=EmotionState(
                dominant_emotion="neutral",
                intensity=0.5
            ),
            continuity_memory=ContinuityMemory(
                locked_facts=[],
                last_scene_summary="Start of the story"
            ),
            render_state=RenderState(
                fps=30,
                aspect_ratio="9:16",
                last_render_status="pending"
            )
        )
        storage.save(state)
        return state

    @staticmethod
    def get_state(story_id: str) -> Optional[CinematicStateGraph]:
        """Retrieves latest state."""
        return storage.load(story_id)

    @staticmethod
    def update_state(story_id: str, scene_result: SceneResult) -> CinematicStateGraph:
        """
        Updates state using scene_result.
        Most important function: deterministic updates.
        """
        state = storage.load(story_id)
        if not state:
            raise ValueError(f"Story ID {story_id} not found. Must create state first.")

        # 1. Update tension (clamped 0-1)
        state.narrative_state.tension = round(max(0.0, min(1.0, 
            state.narrative_state.tension + scene_result.emotion_shift.intensity_delta
        )), 4)

        # 2. Update emotion_state
        state.emotion_state.dominant_emotion = scene_result.emotion_shift.dominant_emotion
        state.emotion_state.intensity = round(max(0.0, min(1.0, 
            state.emotion_state.intensity + scene_result.emotion_shift.intensity_delta
        )), 4)

        # 3. Update character emotions
        for char_update in scene_result.character_updates:
            char_id = char_update.character_id
            if char_id in state.characters:
                state.characters[char_id].current_emotion = char_update.emotion
                state.characters[char_id].emotion_intensity = round(max(0.0, min(1.0, char_update.intensity)), 4)
            else:
                from .models import CharacterState
                state.characters[char_id] = CharacterState(
                    name=char_id,
                    current_emotion=char_update.emotion,
                    emotion_intensity=round(max(0.0, min(1.0, char_update.intensity)), 4)
                )

        # 4. Append continuity_memory.locked_facts
        state.continuity_memory.locked_facts.extend(scene_result.new_facts)

        # 5. Update last_scene_summary
        state.continuity_memory.last_scene_summary = scene_result.scene_summary

        # Increment scene index
        state.narrative_state.current_scene_index += 1

        # 6. Persist updated state
        storage.save(state)
        return state
