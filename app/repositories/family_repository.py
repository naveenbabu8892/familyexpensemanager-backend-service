from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.family import Family, FamilyMember, FamilyInvitation
from app.models.user import User


class FamilyRepository:
    """Data access repository for Families, Memberships, and Invitations."""

    @staticmethod
    async def get_by_id(session: AsyncSession, family_id: uuid.UUID) -> Family | None:
        """Fetch family by primary key."""
        result = await session.execute(select(Family).where(Family.id == family_id))
        return result.scalars().first()

    @staticmethod
    async def create(session: AsyncSession, family: Family) -> Family:
        """Persist a new Family entity."""
        session.add(family)
        await session.flush()
        await session.refresh(family)
        return family

    @staticmethod
    async def update(session: AsyncSession, family: Family) -> Family:
        """Update an existing Family entity."""
        await session.flush()
        await session.refresh(family)
        return family

    @staticmethod
    async def get_user_membership(
        session: AsyncSession, user_id: uuid.UUID
    ) -> FamilyMember | None:
        """Fetch the active family membership for a user."""
        stmt = (
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id, FamilyMember.status == "active")
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_user_family_and_membership(
        session: AsyncSession, user_id: uuid.UUID
    ) -> tuple[Family, FamilyMember] | None:
        """Fetch the user's active family and their membership record together."""
        stmt = (
            select(Family, FamilyMember)
            .join(FamilyMember, FamilyMember.family_id == Family.id)
            .where(FamilyMember.user_id == user_id, FamilyMember.status == "active")
        )
        result = await session.execute(stmt)
        row = result.first()
        if not row:
            return None
        return row[0], row[1]

    @staticmethod
    async def add_member(session: AsyncSession, member: FamilyMember) -> FamilyMember:
        """Add a member to a family."""
        session.add(member)
        await session.flush()
        await session.refresh(member)
        return member

    @staticmethod
    async def get_family_members(
        session: AsyncSession, family_id: uuid.UUID
    ) -> list[tuple[FamilyMember, User]]:
        """Fetch all members of a family along with their User records."""
        stmt = (
            select(FamilyMember, User)
            .join(User, FamilyMember.user_id == User.id)
            .where(FamilyMember.family_id == family_id)
            .order_by(FamilyMember.joined_at.asc())
        )
        result = await session.execute(stmt)
        return result.all()

    @staticmethod
    async def create_invitation(
        session: AsyncSession, invitation: FamilyInvitation
    ) -> FamilyInvitation:
        """Persist a new family invitation."""
        session.add(invitation)
        await session.flush()
        await session.refresh(invitation)
        return invitation

    @staticmethod
    async def get_invitation_by_token(
        session: AsyncSession, token: str
    ) -> FamilyInvitation | None:
        """Lookup an invitation by secure token."""
        stmt = select(FamilyInvitation).where(FamilyInvitation.token == token)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_pending_invitation_by_email(
        session: AsyncSession, family_id: uuid.UUID, email: str
    ) -> FamilyInvitation | None:
        """Check if an active pending invitation exists for an email within a family."""
        stmt = select(FamilyInvitation).where(
            FamilyInvitation.family_id == family_id,
            FamilyInvitation.invited_email == email.lower().strip(),
            FamilyInvitation.status == "pending",
            FamilyInvitation.expires_at > datetime.now(timezone.utc),
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def update_invitation(
        session: AsyncSession, invitation: FamilyInvitation
    ) -> FamilyInvitation:
        """Update invitation record."""
        await session.flush()
        await session.refresh(invitation)
        return invitation
