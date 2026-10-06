from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schemas.auth import (
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def rate_limit_auth(request: Request):
    """Rate limit dependency for authentication endpoints."""
    limiter.check_rate_limit(
        request,
        max_requests=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window_seconds=60,
        key_prefix="auth",
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
    summary="Register New User",
    description="Register a new user account with email, full name, and password.",
)
async def register(
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user and return access + refresh tokens."""
    _, access_token, refresh_token = await AuthService.register_user(db, data)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_auth)],
    summary="User Login",
    description="Authenticate user with email and password to receive access and refresh tokens.",
)
async def login(
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate credentials and return new token pair."""
    _, access_token, refresh_token = await AuthService.authenticate_user(db, data)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_auth)],
    summary="Refresh Access Token",
    description="Rotate refresh token and issue a fresh access and refresh token pair.",
)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token and return new credentials."""
    new_access_token, new_refresh_token = await AuthService.refresh_tokens(
        db, data.refresh_token
    )
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Revoke the provided refresh token session.",
)
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revoke the refresh token."""
    await AuthService.logout_user(db, data.refresh_token)
    return MessageResponse(message="Successfully logged out.")
