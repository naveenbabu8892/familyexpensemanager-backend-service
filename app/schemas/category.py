from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryCreateRequest(BaseModel):
    """Payload to create a family custom category."""
    name: str = Field(..., min_length=1, max_length=50, description="Category name")
    icon: str | None = Field(default=None, max_length=50, description="Material icon identifier")
    color: str | None = Field(default=None, max_length=10, description="Hex color code (e.g. #FF5722)")
    type: str = Field(default="expense", description="Category type: 'expense', 'income', or 'both'")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Category name cannot be empty.")
        return cleaned

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        lowered = v.lower().strip()
        if lowered not in ("expense", "income", "both"):
            raise ValueError("Category type must be 'expense', 'income', or 'both'.")
        return lowered


class CategoryUpdateRequest(BaseModel):
    """Payload to update an existing family category."""
    name: str | None = Field(default=None, min_length=1, max_length=50, description="Category name")
    icon: str | None = Field(default=None, max_length=50, description="Material icon identifier")
    color: str | None = Field(default=None, max_length=10, description="Hex color code (e.g. #FF5722)")
    type: str | None = Field(default=None, description="Category type: 'expense', 'income', or 'both'")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Category name cannot be empty.")
            return cleaned
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None:
            lowered = v.lower().strip()
            if lowered not in ("expense", "income", "both"):
                raise ValueError("Category type must be 'expense', 'income', or 'both'.")
            return lowered
        return v


class CategoryResponse(BaseModel):
    """Category response model."""
    id: uuid.UUID
    family_id: uuid.UUID | None
    name: str
    icon: str | None
    color: str | None
    type: str
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryDeleteResponse(BaseModel):
    """Category deletion confirmation response."""
    message: str
    category_id: uuid.UUID
