from typing import Dict, List
from core.cinematic_state.models import CinematicStateGraph, CharacterState
from .schema import CharacterDirection, DialogueIntent, EmotionalTarget

class CharacterDirector:
    def generate_directions(
        self, state: CinematicStateGraph, target: EmotionalTarget
    ) -> Dict[str, CharacterDirection]:
        """
        Produces behavior notes and directions for each character in the scene.
        """
        directions = {}
        for char_id, char_state in state.characters.items():
            behavior_notes = self._get_behavior_notes(char_state, target)
            
            directions[char_id] = CharacterDirection(
                emotion=char_state.current_emotion,
                intensity=char_state.emotion_intensity,
                behavior_notes=behavior_notes
            )
        return directions

    def _get_behavior_notes(self, char_state: CharacterState, target: EmotionalTarget) -> List[str]:
        """
        Deterministic behavior mapping based on emotion and intensity.
        """
        emotion = char_state.current_emotion.lower()
        intensity = char_state.emotion_intensity
        notes = []

        if "anger" in emotion:
            notes.append("Tense jaw and clenched fists")
            if intensity > 0.7:
                notes.append("Pacing aggressively")
        elif "sadness" in emotion or "grief" in emotion:
            notes.append("Avoids eye contact")
            notes.append("Slumped shoulders")
        elif "joy" in emotion:
            notes.append("Light, expressive movements")
            notes.append("Frequent smiles")
        elif "fear" in emotion or "anxiety" in emotion:
            notes.append("Rapid eye movement")
            notes.append("Fidgeting with hands")
        else:
            notes.append("Neutral, observant posture")

        # React to scene's emotional target
        if target.dominant_emotion != char_state.current_emotion:
            notes.append(f"Internal conflict: showing {char_state.current_emotion} while environment is {target.dominant_emotion}")

        return notes

    def generate_dialogue_intent(
        self, state: CinematicStateGraph, target: EmotionalTarget
    ) -> List[DialogueIntent]:
        """
        Produces dialogue intent for characters based on their state and scene target.
        """
        dialogue_intents = []
        for char_id, char_state in state.characters.items():
            intent = self._determine_intent(char_state, target)
            tone = self._determine_tone(char_state)
            
            dialogue_intents.append(DialogueIntent(
                character_id=char_id,
                intent=intent,
                tone=tone
            ))
        return dialogue_intents

    def _determine_intent(self, char_state: CharacterState, target: EmotionalTarget) -> str:
        emotion = char_state.current_emotion.lower()
        if "anger" in emotion:
            return "Challenge or confront others"
        elif "fear" in emotion:
            return "Seek reassurance or escape"
        elif "joy" in emotion:
            return "Share positive news or celebrate"
        elif "sadness" in emotion:
            return "Express loss or seek comfort"
        return "Observe and comment on the situation"

    def _determine_tone(self, char_state: CharacterState) -> str:
        intensity = char_state.emotion_intensity
        emotion = char_state.current_emotion
        if intensity > 0.8:
            return f"Extreme {emotion}"
        elif intensity < 0.3:
            return f"Subtle {emotion}"
        return emotion
