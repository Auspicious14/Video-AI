from .schema import CameraDirection, CameraDuration, EmotionalTarget

class CameraMapper:
    @staticmethod
    def map_emotion_to_camera(target: EmotionalTarget) -> CameraDirection:
        """
        Maps emotional state to deterministic camera rules.
        """
        emotion = target.dominant_emotion.lower()
        intensity = target.intensity

        # Default camera settings
        style = "cinematic"
        shot_type = "medium shot"
        movement = "static"
        min_duration = 3
        max_duration = 6

        if "anxiety" in emotion or "stress" in emotion or "fear" in emotion:
            style = "handheld instability"
            shot_type = "close-up"
            movement = "jittery"
            min_duration = 2
            max_duration = 4
        elif "grief" in emotion or "sadness" in emotion:
            style = "static close-up"
            shot_type = "extreme close-up"
            movement = "none"
            min_duration = 5
            max_duration = 8
        elif "reflection" in emotion or "contemplation" in emotion or "peace" in emotion:
            style = "wide static frame"
            shot_type = "wide shot"
            movement = "none"
            min_duration = 6
            max_duration = 10
        elif "tension" in emotion or "suspense" in emotion:
            style = "slow push-in"
            shot_type = "medium close-up"
            movement = "push-in"
            min_duration = 4
            max_duration = 7
        elif "anger" in emotion or "rage" in emotion:
            style = "aggressive"
            shot_type = "low angle"
            movement = "fast pan"
            min_duration = 2
            max_duration = 4
        elif "joy" in emotion or "excitement" in emotion:
            style = "dynamic"
            shot_type = "medium shot"
            movement = "tracking"
            min_duration = 3
            max_duration = 5

        # Adjust duration based on intensity
        if intensity > 0.8:
            min_duration = max(1, min_duration - 1)
            max_duration = max(2, max_duration - 1)

        return CameraDirection(
            style=style,
            shot_type=shot_type,
            movement=movement,
            duration_sec=CameraDuration(min=min_duration, max=max_duration)
        )
