from fastapi import APIRouter, Depends

from gateway.core.auth import User, current_user

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
async def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role}
