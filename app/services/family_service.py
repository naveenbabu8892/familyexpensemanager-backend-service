from datetime import datetime, timedelta, timezone
import secrets
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import Family, FamilyMember, FamilyInvitation
from app.models.relationship import FamilyRelationship
from app.models.user import User
from app.repositories.family_repository import FamilyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.family import (
    AcceptInvitationRequest,
    FamilyCreateRequest,
    FamilyInvitationResponse,
    FamilyInviteRequest,
    FamilyMemberResponse,
    FamilyResponse,
    FamilyUpdateRequest,
)


class FamilyService:
    """Business logic for family creation, membership management, and invitations."""

    @staticmethod
    async def create_family(
        session: AsyncSession, user: User, data: FamilyCreateRequest
    ) -> FamilyResponse:
        """
        Create a new family.
        Rules:
        - A user can only belong to one active family.
        - The creator is assigned the 'owner' role.
        """
        existing_membership = await FamilyRepository.get_user_membership(session, user.id)
        if existing_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already belongs to an active family. You must leave or delete it before creating a new one.",
            )

        family = Family(
            name=data.name.strip(),
            currency=data.currency.upper().strip(),
            timezone=data.timezone.strip(),
            created_by=user.id,
        )
        created_family = await FamilyRepository.create(session, family)

        # Creator automatically becomes the OWNER
        owner_member = FamilyMember(
            family_id=created_family.id,
            user_id=user.id,
            role="owner",
            relationship="other",
            status="active",
        )
        await FamilyRepository.add_member(session, owner_member)

        return FamilyResponse(
            id=created_family.id,
            name=created_family.name,
            currency=created_family.currency,
            timezone=created_family.timezone,
            created_by=created_family.created_by,
            created_at=created_family.created_at,
            updated_at=created_family.updated_at,
            user_role="owner",
        )

    @staticmethod
    async def get_current_family(
        session: AsyncSession, user: User
    ) -> FamilyResponse:
        """Fetch the authenticated user's active family."""
        result = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family yet. Create or join one first.",
            )

        family, membership = result
        return FamilyResponse(
            id=family.id,
            name=family.name,
            currency=family.currency,
            timezone=family.timezone,
            created_by=family.created_by,
            created_at=family.created_at,
            updated_at=family.updated_at,
            user_role=membership.role,
        )

    @staticmethod
    async def update_current_family(
        session: AsyncSession, user: User, data: FamilyUpdateRequest
    ) -> FamilyResponse:
        """
        Update current family details.
        Rules:
        - Only family owners can modify family settings.
        """
        result = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )

        family, membership = result
        if membership.role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the family owner has permission to update family settings.",
            )

        if data.name is not None:
            family.name = data.name.strip()
        if data.currency is not None:
            family.currency = data.currency.upper().strip()
        if data.timezone is not None:
            family.timezone = data.timezone.strip()

        updated_family = await FamilyRepository.update(session, family)
        return FamilyResponse(
            id=updated_family.id,
            name=updated_family.name,
            currency=updated_family.currency,
            timezone=updated_family.timezone,
            created_by=updated_family.created_by,
            created_at=updated_family.created_at,
            updated_at=updated_family.updated_at,
            user_role=membership.role,
        )

    @staticmethod
    async def invite_member(
        session: AsyncSession, user: User, data: FamilyInviteRequest
    ) -> FamilyInvitationResponse:
        """
        Send a secure invitation to a spouse/family member.
        Rules:
        - Caller must be an owner of the active family.
        - Cannot invite oneself.
        - Cannot invite an existing active member of the same family.
        - Prevents multiple active pending invitations for the same email.
        """
        result = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )

        family, membership = result
        if membership.role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the family owner can invite new members.",
            )

        normalized_email = data.invited_email.lower().strip()
        if normalized_email == user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot invite yourself to your own family.",
            )

        # Check if recipient is already a member
        target_user = await UserRepository.get_by_email(session, normalized_email)
        if target_user:
            existing_target_membership = await FamilyRepository.get_user_membership(
                session, target_user.id
            )
            if existing_target_membership and existing_target_membership.family_id == family.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This user is already an active member of this family.",
                )

        # Check for existing active pending invitation
        existing_invite = await FamilyRepository.get_pending_invitation_by_email(
            session, family.id, normalized_email
        )
        if existing_invite:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pending invitation for this email address already exists.",
            )

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        rel_value = data.relationship.value if hasattr(data.relationship, "value") else str(data.relationship)

        invitation = FamilyInvitation(
            family_id=family.id,
            invited_by=user.id,
            invited_email=normalized_email,
            relationship=rel_value,
            token=token,
            status="pending",
            expires_at=expires_at,
        )
        created_invitation = await FamilyRepository.create_invitation(session, invitation)

        return FamilyInvitationResponse(
            id=created_invitation.id,
            family_id=created_invitation.family_id,
            invited_email=created_invitation.invited_email,
            relationship=created_invitation.relationship,
            relationship_label=FamilyRelationship.get_relationship_label(created_invitation.relationship),
            status=created_invitation.status,
            expires_at=created_invitation.expires_at,
            created_at=created_invitation.created_at,
            token=created_invitation.token,
        )

    @staticmethod
    async def accept_invitation(
        session: AsyncSession, user: User, data: AcceptInvitationRequest
    ) -> FamilyResponse:
        """
        Accept an invitation to join a family.
        Rules:
        - Token must exist and be in 'pending' status.
        - Token must not be expired.
        - Authenticated user's email must match the invited email.
        - User cannot already belong to another family.
        - Newly joined user receives 'member' role and the relationship specified in the invitation.
        """
        invitation = await FamilyRepository.get_invitation_by_token(session, data.token.strip())
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid invitation token.",
            )

        if invitation.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This invitation has already been {invitation.status}.",
            )

        now = datetime.now(timezone.utc)
        if invitation.expires_at < now:
            invitation.status = "expired"
            await FamilyRepository.update_invitation(session, invitation)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation has expired. Please request a new invitation.",
            )

        if invitation.invited_email.lower() != user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This invitation was sent to {invitation.invited_email}. Please log in with that account to accept it.",
            )

        # Check if the accepting user already belongs to a family
        existing_membership = await FamilyRepository.get_user_membership(session, user.id)
        if existing_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already belong to an active family. You must leave it before joining a new one.",
            )

        # Mark invitation as accepted
        invitation.status = "accepted"
        await FamilyRepository.update_invitation(session, invitation)

        # Add member with 'member' role and copy invitation relationship
        new_member = FamilyMember(
            family_id=invitation.family_id,
            user_id=user.id,
            role="member",
            relationship=invitation.relationship or "other",
            status="active",
        )
        await FamilyRepository.add_member(session, new_member)

        family = await FamilyRepository.get_by_id(session, invitation.family_id)
        if not family:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found.")

        return FamilyResponse(
            id=family.id,
            name=family.name,
            currency=family.currency,
            timezone=family.timezone,
            created_by=family.created_by,
            created_at=family.created_at,
            updated_at=family.updated_at,
            user_role="member",
        )

    @staticmethod
    async def list_family_members(
        session: AsyncSession, user: User
    ) -> list[FamilyMemberResponse]:
        """Fetch all members of the authenticated user's family."""
        result = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )

        family, _ = result
        members_data = await FamilyRepository.get_family_members(session, family.id)

        responses = []
        for member, member_user in members_data:
            rel = getattr(member, "relationship", "other") or "other"
            responses.append(
                FamilyMemberResponse(
                    id=member.id,
                    family_id=member.family_id,
                    user_id=member.user_id,
                    name=member_user.full_name,
                    role=member.role,
                    relationship=rel,
                    relationship_label=FamilyRelationship.get_relationship_label(rel),
                    status=member.status,
                    joined_at=member.joined_at,
                    user_full_name=member_user.full_name,
                    user_email=member_user.email,
                    user_avatar_url=member_user.avatar_url,
                )
            )
        return responses
