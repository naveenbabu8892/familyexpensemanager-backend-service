from datetime import date, datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class IncomeCreateRequest(BaseModel):
    """Payload to record a new family income."""
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Monetary income amount")
    currency: str | None = Field(default=None, min_length=3, max_length=3, description="3-character currency code (defaults to family currency)")
    category_id: uuid.UUID | None = Field(default=None, description="Optional income category ID")
    income_date: date = Field(..., description="Date the income was received")
    received_by: uuid.UUID | None = Field(default=None, description="User ID of the recipient family member (defaults to current user)")
    title: str = Field(..., min_length=1, max_length=150, description="Income title/source (e.g. Monthly Salary)")
    description: str | None = Field(default=None, description="Optional detailed notes")


class IncomeUpdateRequest(BaseModel):
    """Payload to update an existing income record."""
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category_id: uuid.UUID | None = None
    income_date: date | None = None
    received_by: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None


class IncomeResponse(BaseModel):
    """Income response model with populated relation details."""
    id: uuid.UUID
    family_id: uuid.UUID
    received_by: uuid.UUID
    category_id: uuid.UUID | None
    amount: Decimal
    currency: str
    income_date: date
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    category_name: str | None = None
    received_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class IncomeListResponse(BaseModel):
    """Paginated response containing list of income entries and statistics."""
    items: list[IncomeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    total_amount: Decimal
