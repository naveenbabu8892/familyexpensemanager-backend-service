from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.family import (
    AcceptInvitationRequest,
    FamilyCreateRequest,
    FamilyInvitationResponse,
    FamilyInviteRequest,
    FamilyMemberResponse,
    FamilyResponse,
    FamilyUpdateRequest,
    RelationshipItem,
    RelationshipListResponse,
)
from app.models.relationship import FamilyRelationship
from app.services.family_service import FamilyService

router = APIRouter(prefix="/families", tags=["Families"])


@router.post(
    "",
    response_model=FamilyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Family",
    description="Create a new family household. The creator is automatically assigned the OWNER role.",
)
async def create_family(
    data: FamilyCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new family household."""
    return await FamilyService.create_family(db, current_user, data)


@router.get(
    "/current",
    response_model=FamilyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Family",
    description="Retrieve details of the authenticated user's active family.",
)
async def get_current_family(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the current user's family."""
    return await FamilyService.get_current_family(db, current_user)


@router.put(
    "/current",
    response_model=FamilyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Current Family",
    description="Update family name, currency, or timezone. Requires OWNER role.",
)
async def update_current_family(
    data: FamilyUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update settings for the current user's family."""
    return await FamilyService.update_current_family(db, current_user, data)


@router.post(
    "/invite",
    response_model=FamilyInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite Family Member",
    description="Send a secure invitation to a family member with their relationship. Requires OWNER role.",
)
@router.post(
    "/invitations",
    response_model=FamilyInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite Family Member (REST alias)",
    description="Send a secure invitation to a family member with their relationship. Requires OWNER role.",
)
async def invite_member(
    data: FamilyInviteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new member to the family."""
    return await FamilyService.invite_member(db, current_user, data)


@router.post(
    "/invite/accept",
    response_model=FamilyResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept Family Invitation",
    description="Accept an invitation using a secure token and join the family as a MEMBER.",
)
async def accept_invitation(
    data: AcceptInvitationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept an invitation to join a family."""
    return await FamilyService.accept_invitation(db, current_user, data)


@router.get(
    "/members",
    response_model=list[FamilyMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List Family Members",
    description="List all members of the current user's family with their roles and profile details.",
)
async def list_family_members(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List members belonging to the current user's family."""
    return await FamilyService.list_family_members(db, current_user)


@router.get(
    "/relationships",
    response_model=RelationshipListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Family Relationships",
    description="List all available family relationships supported by the system.",
)
async def list_relationships():
    """Return available family relationships."""
    items = [
        RelationshipItem(value=rel.value, label=rel.label)
        for rel in FamilyRelationship
    ]
    return RelationshipListResponse(data=items)
