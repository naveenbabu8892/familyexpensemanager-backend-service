from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Fetch the authenticated user's profile details.",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Return the currently authenticated user."""
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Current User Profile",
    description="Update the authenticated user's profile information.",
)
async def update_me(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update profile attributes of the authenticated user."""
    if data.full_name is not None:
        current_user.full_name = data.full_name.strip()

    if data.phone is not None:
        new_phone = data.phone.strip() if data.phone else None
        if new_phone != current_user.phone and new_phone is not None:
            existing_phone = await UserRepository.get_by_phone(db, new_phone)
            if existing_phone and existing_phone.id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This phone number is already associated with another account.",
                )
        current_user.phone = new_phone

    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url.strip() if data.avatar_url else None

    updated_user = await UserRepository.update(db, current_user)
    return updated_user
