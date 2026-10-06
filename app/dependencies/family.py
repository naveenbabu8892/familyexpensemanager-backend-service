from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.family import Family, FamilyMember
from app.models.user import User
from app.repositories.family_repository import FamilyRepository


async def get_current_family_context(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[Family, FamilyMember]:
    """
    Security Dependency: Resolve the authenticated user's active family and membership.
    Ensures users can NEVER access or manipulate any other family's data.
    """
    result = await FamilyRepository.get_user_family_and_membership(db, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You do not belong to any family. Please create or join one first.",
        )
    return result


async def require_family_owner(
    context: tuple[Family, FamilyMember] = Depends(get_current_family_context),
) -> tuple[Family, FamilyMember]:
    """Authorization Dependency: Ensures the current user is the owner of the family."""
    _, membership = context
    if membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the family owner has permission to perform this action.",
        )
    return context
