from typing import List
from core.scene_intent.schema import SceneIntent, DialogueIntent
from core.memory_engine.schema import CharacterIdentityProfile
from .schema import DialogueBlock

class DialogueDirector:
    """
    Responsible for generating emotionally grounded dialogue, conversational realism,
    pacing realism, silence handling, and interruption logic.
    """
    
    def generate_dialogue_blocks(
        self, 
        scene_intent: SceneIntent, 
        character_profiles: List[CharacterIdentityProfile]
    ) -> List[DialogueBlock]:
        """
        Generates a sequence of dialogue blocks based on scene intent and character profiles.
        Prioritizes restraint, realism, and emotional subtlety.
        """
        dialogue_blocks = []
        
        # Map character profiles for quick lookup
        char_map = {cp.character_id: cp for cp in character_profiles}
        
        for intent in scene_intent.dialogue_intent:
            char_id = intent.character_id
            profile = char_map.get(char_id)
            
            # Determine delivery and pacing style based on character profile and intent tone
            delivery_style = self._map_delivery_style(intent, profile)
            pacing_style = self._map_pacing_style(intent, profile)
            
            # Generate the actual line (in a real system, this might call an LLM)
            # For this implementation, we use the intent as a base or placeholder
            line = self._generate_realistic_line(intent, profile)
            
            block = DialogueBlock(
                character_id=char_id,
                line=line,
                emotional_subtext=intent.tone,
                delivery_style=delivery_style,
                pacing_style=pacing_style,
                pause_before_ms=self._calculate_pause_before(intent),
                pause_after_ms=self._calculate_pause_after(intent)
            )
            dialogue_blocks.append(block)
            
        return dialogue_blocks

    def _map_delivery_style(self, intent: DialogueIntent, profile: CharacterIdentityProfile) -> str:
        # Subtle mapping logic: high intensity + vulnerability -> whispered/broken
        if "vulnerable" in intent.tone.lower() or "sad" in intent.tone.lower():
            return "whispered" if "hushed" in profile.voice_profile.vocal_tone.lower() else "soft"
        if "angry" in intent.tone.lower():
            return "strained" if "low" in profile.voice_profile.vocal_tone.lower() else "sharp"
        return "steady"

    def _map_pacing_style(self, intent: DialogueIntent, profile: CharacterIdentityProfile) -> str:
        # Pacing based on character habits and current emotional state
        base_pacing = profile.voice_profile.pacing_style
        if "anxious" in intent.tone.lower() or "excited" in intent.tone.lower():
            return "fast_irregular"
        if "thoughtful" in intent.tone.lower() or "depressed" in intent.tone.lower():
            return "slow_deliberate"
        return base_pacing

    def _generate_realistic_line(self, intent: DialogueIntent, profile: CharacterIdentityProfile) -> str:
        # This is a placeholder for LLM-based dialogue generation.
        # It ensures the output follows the rules: restrained, natural, imperfect.
        # Example: instead of "I am very upset that you left me", 
        # it might produce "You... you just walked out. Without a word."
        
        # Simulating realistic dialogue generation logic:
        raw_intent = intent.intent
        if "confession" in raw_intent.lower():
            return "I didn't think... I didn't think it would happen like this."
        elif "confrontation" in raw_intent.lower():
            return "Is that really what you're going with? After everything?"
        
        return f"[Generated dialogue for: {raw_intent}]"

    def _calculate_pause_before(self, intent: DialogueIntent) -> int:
        # Hesitation before speaking based on tone
        if "hesitant" in intent.tone.lower() or "guilty" in intent.tone.lower():
            return 800
        return 200

    def _calculate_pause_after(self, intent: DialogueIntent) -> int:
        # Emotional weight after speaking
        if "heavy" in intent.tone.lower() or "final" in intent.tone.lower():
            return 1200
        return 400
