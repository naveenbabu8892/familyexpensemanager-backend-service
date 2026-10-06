from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class BudgetCreateRequest(BaseModel):
    """Payload to create a new monthly category budget."""
    category_id: uuid.UUID = Field(..., description="Target expense category UUID")
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Allocated budget amount (> 0)")
    month: int = Field(..., ge=1, le=12, description="Calendar month (1 - 12)")
    year: int = Field(..., ge=2000, le=2100, description="Calendar year (>= 2000)")


class BudgetUpdateRequest(BaseModel):
    """Payload to update an existing budget."""
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2, description="New allocated budget amount")
    month: int | None = Field(default=None, ge=1, le=12, description="New calendar month (1 - 12)")
    year: int | None = Field(default=None, ge=2000, le=2100, description="New calendar year (>= 2000)")
    category_id: uuid.UUID | None = Field(default=None, description="New category UUID")


class BudgetResponse(BaseModel):
    """Comprehensive budget response with SQL-calculated spending and warning statuses."""
    id: uuid.UUID
    family_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str | None = None
    category_icon: str | None = None
    category_color: str | None = None
    month: int
    year: int
    amount: Decimal  # Allocated budget amount
    amount_spent: Decimal  # Total spent in this category and month/year
    remaining_amount: Decimal  # amount - amount_spent (can be negative if over budget)
    percentage_used: Decimal  # (amount_spent / amount) * 100 rounded to 2 decimal places
    warning_level: str  # "normal", "75%", "90%", "100%+"
    has_warning: bool  # True if percentage_used >= 75%
    is_exceeded: bool  # True if percentage_used >= 100%
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetDeleteResponse(BaseModel):
    """Budget deletion confirmation response."""
    message: str
    budget_id: uuid.UUID
