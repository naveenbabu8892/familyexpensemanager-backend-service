import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Data access repository for User entities."""

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
        """Fetch user by primary key."""
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> User | None:
        """Fetch user by unique email."""
        result = await session.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalars().first()

    @staticmethod
    async def get_by_phone(session: AsyncSession, phone: str) -> User | None:
        """Fetch user by unique phone number."""
        result = await session.execute(select(User).where(User.phone == phone.strip()))
        return result.scalars().first()

    @staticmethod
    async def create(session: AsyncSession, user: User) -> User:
        """Persist a new User."""
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    @staticmethod
    async def update(session: AsyncSession, user: User) -> User:
        """Update an existing User."""
        await session.flush()
        await session.refresh(user)
        return user
