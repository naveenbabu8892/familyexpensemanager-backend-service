from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.relationship import FamilyRelationship


class RelationshipItem(BaseModel):
    """Available family relationship option."""
    value: str = Field(..., description="Stable lowercase identifier for relationship")
    label: str = Field(..., description="User-friendly capitalized display label")


class RelationshipListResponse(BaseModel):
    """Dynamic relationship choices list."""
    data: list[RelationshipItem]


class FamilyCreateRequest(BaseModel):
    """Payload to create a new family."""
    name: str = Field(..., min_length=2, max_length=100, description="Family name")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="3-character ISO currency code")
    timezone: str = Field(default="UTC", min_length=2, max_length=50, description="Timezone identifier")


class FamilyUpdateRequest(BaseModel):
    """Payload to update family settings."""
    name: str | None = Field(default=None, min_length=2, max_length=100)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, min_length=2, max_length=50)


class FamilyResponse(BaseModel):
    """Family details response."""
    id: uuid.UUID
    name: str
    currency: str
    timezone: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    user_role: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FamilyInviteRequest(BaseModel):
    """Payload to invite a family member with their relationship."""
    invited_email: EmailStr = Field(..., description="Email address of the family member to invite")
    relationship: FamilyRelationship = Field(
        default=FamilyRelationship.OTHER,
        description="Relationship of the invited member (e.g. husband, wife, father, mother, etc.)",
    )


class FamilyInvitationResponse(BaseModel):
    """Invitation details response."""
    id: uuid.UUID
    family_id: uuid.UUID
    invited_email: EmailStr
    relationship: str
    relationship_label: str
    status: str
    expires_at: datetime
    created_at: datetime
    token: str

    model_config = ConfigDict(from_attributes=True)


class AcceptInvitationRequest(BaseModel):
    """Payload to accept an invitation."""
    token: str = Field(..., min_length=1, description="Secure invitation token")


class FamilyMemberResponse(BaseModel):
    """Family member representation with user profile and relationship information."""
    id: uuid.UUID
    family_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    role: str
    relationship: str
    relationship_label: str
    status: str
    joined_at: datetime
    user_full_name: str
    user_email: EmailStr
    user_avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)
