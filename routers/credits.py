from fastapi import APIRouter
import store

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/{email}")
def get_credits(email: str):
    return {"email": email, "credits": store.get_credits(email)}