from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class AppearanceProfile(BaseModel):
    age_range: str
    skin_tone: str
    facial_structure: str
    hairstyle: str
    body_type: str
    wardrobe_style: str

class VoiceProfile(BaseModel):
    vocal_tone: str
    pacing_style: str
    speech_patterns: List[str]

class BehaviorProfile(BaseModel):
    posture_style: str
    emotional_expression_style: str
    gesture_patterns: List[str]

class EmotionalBaseline(BaseModel):
    dominant_traits: List[str]
    emotional_sensitivity: float = Field(ge=0.0, le=1.0)

class ContinuityConstraints(BaseModel):
    immutable_traits: List[str] = Field(default_factory=list)
    mutable_traits: List[str] = Field(default_factory=list)

class ReferenceAssets(BaseModel):
    canonical_images: List[str] = Field(default_factory=list)
    canonical_voice_refs: List[str] = Field(default_factory=list)

class CharacterIdentityProfile(BaseModel):
    character_id: str
    canonical_name: str
    appearance_profile: AppearanceProfile
    voice_profile: VoiceProfile
    behavior_profile: BehaviorProfile
    emotional_baseline: EmotionalBaseline
    continuity_constraints: ContinuityConstraints
    reference_assets: ReferenceAssets

class VisualProfile(BaseModel):
    architecture_style: str
    lighting_style: str
    color_palette: List[str]
    texture_profile: List[str]

class AtmosphereProfile(BaseModel):
    ambient_audio: str
    emotional_feeling: str

class EnvironmentContinuityConstraints(BaseModel):
    immutable_elements: List[str] = Field(default_factory=list)
    mutable_elements: List[str] = Field(default_factory=list)

class EnvironmentReferenceAssets(BaseModel):
    canonical_images: List[str] = Field(default_factory=list)

class EnvironmentIdentityProfile(BaseModel):
    environment_id: str
    canonical_name: str
    visual_profile: VisualProfile
    atmosphere_profile: AtmosphereProfile
    continuity_constraints: EnvironmentContinuityConstraints
    reference_assets: EnvironmentReferenceAssets

class MemoryEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    story_id: str
    scene_id: str
    description: str
    affected_traits: Dict[str, str] = Field(
        default_factory=dict,
        description="trait_name -> new_value"
    )

class EmotionalShift(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    story_id: str
    scene_id: str
    character_id: str
    from_emotion: str
    to_emotion: str
    intensity_shift: float

class ContinuityEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    story_id: str
    scene_id: str
    lock_type: Literal["wardrobe", "hairstyle", "prop", "lighting", "damage"]
    description: str
    metadata: Dict[str, str] = Field(default_factory=dict)

class MemoryTimeline(BaseModel):
    story_id: str
    character_history: Dict[str, List[MemoryEvent]] = Field(
        default_factory=dict,
        description="character_id -> list of memory events"
    )
    environment_history: Dict[str, List[MemoryEvent]] = Field(
        default_factory=dict,
        description="environment_id -> list of memory events"
    )
    emotional_history: List[EmotionalShift] = Field(default_factory=list)
    continuity_events: List[ContinuityEvent] = Field(default_factory=list)
