from datetime import datetime, timezone
import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import RefreshToken


class TokenRepository:
    """Data access repository for RefreshToken records."""

    @staticmethod
    async def create_refresh_token(
        session: AsyncSession,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Create and persist a new hashed refresh token."""
        token_record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        session.add(token_record)
        await session.flush()
        await session.refresh(token_record)
        return token_record

    @staticmethod
    async def get_by_token_hash(session: AsyncSession, token_hash: str) -> RefreshToken | None:
        """Find a refresh token record by its SHA-256 hash."""
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalars().first()

    @staticmethod
    async def revoke_token(session: AsyncSession, token_hash: str) -> bool:
        """Mark a refresh token as revoked."""
        result = await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked=True)
        )
        await session.flush()
        return result.rowcount > 0

    @staticmethod
    async def revoke_all_user_tokens(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Revoke all active tokens for a specific user."""
        result = await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await session.flush()
        return result.rowcount
