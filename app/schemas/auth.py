from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Payload for new user registration."""
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name of user")
    email: EmailStr = Field(..., description="Valid user email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password (min 8 characters)")
    phone: str | None = Field(default=None, max_length=20, description="Optional phone number")


class UserLoginRequest(BaseModel):
    """Payload for user login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    """Response containing JWT access token and refresh token."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Payload for refreshing an expired access token."""
    refresh_token: str = Field(..., min_length=1, description="Cryptographic refresh token")


class LogoutRequest(BaseModel):
    """Payload for logging out and revoking a refresh token."""
    refresh_token: str = Field(..., min_length=1, description="Refresh token to revoke")


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
