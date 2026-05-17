from fastapi import APIRouter, HTTPException
from core.cinematic_state.service import CinematicStateService
from core.scene_intent.service import generate_scene_intent
from core.scene_intent.schema import SceneIntent

router = APIRouter(prefix="/scene-intent", tags=["scene-intent"])

@router.get("/{story_id}", response_model=SceneIntent)
async def get_scene_intent(story_id: str):
    """
    Generates structured cinematic intent based on current state.
    """
    state = CinematicStateService.get_state(story_id)
    if not state:
        raise HTTPException(status_code=404, detail="Cinematic state not found. Create it first.")
    
    try:
        intent = generate_scene_intent(state)
        return intent
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate scene intent: {str(e)}")
