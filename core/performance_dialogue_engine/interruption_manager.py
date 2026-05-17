from typing import List
from core.scene_intent.schema import SceneIntent
from .schema import DialogueBlock, InterruptionPoint

class InterruptionManager:
    """
    Handles overlapping speech, interrupted dialogue, emotional cutoffs, 
    and conversational realism.
    """
    
    def detect_interruption_points(
        self, 
        scene_intent: SceneIntent, 
        dialogue_blocks: List[DialogueBlock]
    ) -> List[InterruptionPoint]:
        """
        Identifies moments where one character should interrupt another.
        """
        interruption_points = []
        
        # We look for high tension or specific dialogue intents that suggest conflict
        if scene_intent.emotional_target.intensity < 0.6:
            return [] # Low intensity rarely results in interruptions
            
        # Scan dialogue blocks for potential overlaps
        for i in range(len(dialogue_blocks) - 1):
            current_block = dialogue_blocks[i]
            next_block = dialogue_blocks[i+1]
            
            # If characters are different and intensity is high, trigger an interruption
            if current_block.character_id != next_block.character_id:
                if "aggressive" in current_block.emotional_subtext.lower() or "urgent" in next_block.emotional_subtext.lower():
                    # Interruption happens towards the end of the current block
                    current_duration = len(current_block.line.split()) * 400
                    interruption_ts = int(current_duration * 0.85)
                    
                    point = InterruptionPoint(
                        timestamp_ms=interruption_ts,
                        interrupted_character_id=current_block.character_id,
                        interrupting_character_id=next_block.character_id,
                        intensity=scene_intent.emotional_target.intensity
                    )
                    interruption_points.append(point)
                    
        return interruption_points
