from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    get_refresh_token_expiration,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserLoginRequest, UserRegisterRequest


class AuthService:
    """Service orchestrating user registration, authentication, token rotation, and revocation."""

    @staticmethod
    async def register_user(
        session: AsyncSession, data: UserRegisterRequest
    ) -> tuple[User, str, str]:
        """Register a new user, preventing duplicate emails, and issue JWT + refresh token."""
        normalized_email = data.email.lower().strip()
        existing_user = await UserRepository.get_by_email(session, normalized_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        if data.phone:
            existing_phone = await UserRepository.get_by_phone(session, data.phone)
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A user with this phone number already exists.",
                )

        # Hash password with Argon2
        hashed_password = get_password_hash(data.password)

        user = User(
            full_name=data.full_name.strip(),
            email=normalized_email,
            phone=data.phone.strip() if data.phone else None,
            password_hash=hashed_password,
            is_active=True,
        )
        created_user = await UserRepository.create(session, user)

        # Issue tokens
        access_token = create_access_token(
            data={"sub": str(created_user.id), "email": created_user.email}
        )
        raw_refresh_token = generate_refresh_token()
        hashed_rf = hash_token(raw_refresh_token)
        expires_at = get_refresh_token_expiration()

        await TokenRepository.create_refresh_token(
            session=session,
            user_id=created_user.id,
            token_hash=hashed_rf,
            expires_at=expires_at,
        )

        return created_user, access_token, raw_refresh_token

    @staticmethod
    async def authenticate_user(
        session: AsyncSession, data: UserLoginRequest
    ) -> tuple[User, str, str]:
        """Authenticate user credentials and issue new token pair."""
        normalized_email = data.email.lower().strip()
        user = await UserRepository.get_by_email(session, normalized_email)

        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact support.",
            )

        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        raw_refresh_token = generate_refresh_token()
        hashed_rf = hash_token(raw_refresh_token)
        expires_at = get_refresh_token_expiration()

        await TokenRepository.create_refresh_token(
            session=session,
            user_id=user.id,
            token_hash=hashed_rf,
            expires_at=expires_at,
        )

        return user, access_token, raw_refresh_token

    @staticmethod
    async def refresh_tokens(
        session: AsyncSession, refresh_token_str: str
    ) -> tuple[str, str]:
        """
        Rotate refresh token:
        1. Validate token hash and revocation status.
        2. Verify expiration and user status.
        3. Revoke current token.
        4. Issue and store new token pair.
        """
        token_hash = hash_token(refresh_token_str)
        token_record = await TokenRepository.get_by_token_hash(session, token_hash)

        if not token_record or token_record.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if token_record.expires_at < datetime.now(timezone.utc):
            await TokenRepository.revoke_token(session, token_hash)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await UserRepository.get_by_id(session, token_record.user_id)
        if not user or not user.is_active:
            await TokenRepository.revoke_token(session, token_hash)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive or not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 1. Revoke the old token (Token Rotation policy)
        await TokenRepository.revoke_token(session, token_hash)

        # 2. Issue new access token and new refresh token
        new_access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        new_raw_refresh_token = generate_refresh_token()
        new_token_hash = hash_token(new_raw_refresh_token)
        new_expires_at = get_refresh_token_expiration()

        await TokenRepository.create_refresh_token(
            session=session,
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
        )

        return new_access_token, new_raw_refresh_token

    @staticmethod
    async def logout_user(session: AsyncSession, refresh_token_str: str) -> None:
        """Revoke the refresh token on logout."""
        token_hash = hash_token(refresh_token_str)
        await TokenRepository.revoke_token(session, token_hash)
