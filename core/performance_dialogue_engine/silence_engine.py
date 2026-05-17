from typing import List
from core.shot_planner.schema import Shot
from .schema import DialogueBlock, SilenceWindow

class SilenceEngine:
    """
    Responsible for intentional silence, emotional breathing room, 
    pause placement, and conversational realism.
    """
    
    def generate_silence_windows(
        self, 
        shot: Shot, 
        dialogue_blocks: List[DialogueBlock]
    ) -> List[SilenceWindow]:
        """
        Identifies and defines windows of intentional silence within a shot.
        """
        silence_windows = []
        
        # Calculate the gaps between dialogue blocks or before/after them
        # This creates the "breathing room" required for cinematic realism.
        
        current_time_ms = 0
        shot_duration_ms = int(shot.duration_sec * 1000)
        
        for block in dialogue_blocks:
            # If there's a pause before the block, it's a silence window
            if block.pause_before_ms > 200:
                silence_windows.append(SilenceWindow(
                    timestamp_ms=current_time_ms,
                    duration_ms=block.pause_before_ms,
                    emotional_quality=self._determine_silence_quality(block.emotional_subtext, "pre")
                ))
            
            # Skip the dialogue block duration (mocked here as word count * 300ms)
            dialogue_duration = len(block.line.split()) * 400
            current_time_ms += block.pause_before_ms + dialogue_duration
            
            # If there's a pause after the block, it's a silence window
            if block.pause_after_ms > 200:
                silence_windows.append(SilenceWindow(
                    timestamp_ms=current_time_ms,
                    duration_ms=block.pause_after_ms,
                    emotional_quality=self._determine_silence_quality(block.emotional_subtext, "post")
                ))
            
            current_time_ms += block.pause_after_ms
            
        # If there's time left in the shot after all dialogue, add a final silence window
        if current_time_ms < shot_duration_ms:
            silence_windows.append(SilenceWindow(
                timestamp_ms=current_time_ms,
                duration_ms=shot_duration_ms - current_time_ms,
                emotional_quality="lingering_aftermath"
            ))
            
        return silence_windows

    def _determine_silence_quality(self, subtext: str, position: str) -> str:
        if "tense" in subtext.lower() or "angry" in subtext.lower():
            return "loaded_tension"
        if "sad" in subtext.lower() or "vulnerable" in subtext.lower():
            return "heavy_reflection"
        if position == "pre":
            return "anticipatory_hesitation"
        return "natural_breath"
