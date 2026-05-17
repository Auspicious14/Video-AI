from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field

class FFmpegPlan(BaseModel):
    composition_type: str
    motion_preset: str
    transition_type: str

class AIMotionPlan(BaseModel):
    enabled: bool
    model: str
    timeout_sec: int
    fallback_strategy: str

class AudioPlan(BaseModel):
    tts_provider: str
    emotional_tone: str
    pacing: str

class ContinuityConstraints(BaseModel):
    preserve_character_identity: bool = True
    preserve_environment: bool = True
    preserve_camera_language: bool = True

class AssetRequirements(BaseModel):
    requires_image_generation: bool
    requires_video_generation: bool
    requires_voice: bool
    requires_lipsync: bool

class GenerationPlan(BaseModel):
    image_prompt_context: str
    motion_prompt_context: str
    voice_direction: str

class RenderShot(BaseModel):
    shot_id: str
    render_strategy: Literal["deterministic", "ai_motion", "hybrid"]
    
    asset_requirements: AssetRequirements
    generation_plan: GenerationPlan
    ffmpeg_plan: FFmpegPlan
    ai_motion_plan: AIMotionPlan
    audio_plan: AudioPlan
    continuity_constraints: ContinuityConstraints
    
    execution_order: int

class RenderExecutionPlan(BaseModel):
    story_id: str
    scene_id: str
    shots: List[RenderShot]
