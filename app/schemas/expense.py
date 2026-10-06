from datetime import date, datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ExpenseCreateRequest(BaseModel):
    """Payload to record a new family expense."""
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Expense amount (strictly positive)")
    currency: str | None = Field(default=None, min_length=3, max_length=3, description="3-character ISO currency code (defaults to family currency)")
    category_id: uuid.UUID = Field(..., description="ID of the expense category")
    expense_date: date = Field(..., description="Date the expense occurred")
    payment_method: str = Field(default="cash", max_length=30, description="Payment method: cash, credit_card, debit_card, upi, bank_transfer, etc.")
    title: str = Field(..., min_length=1, max_length=150, description="Short title of the expense")
    description: str | None = Field(default=None, description="Optional detailed notes")
    paid_by: uuid.UUID | None = Field(default=None, description="User ID of the member who paid (defaults to current user)")
    is_shared: bool = Field(default=True, description="Whether this is a shared household expense")


class ExpenseUpdateRequest(BaseModel):
    """Payload to update an existing expense."""
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category_id: uuid.UUID | None = None
    expense_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    paid_by: uuid.UUID | None = None
    is_shared: bool | None = None


class ExpenseResponse(BaseModel):
    """Expense representation with associated entity names."""
    id: uuid.UUID
    family_id: uuid.UUID
    created_by: uuid.UUID
    paid_by: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    currency: str
    expense_date: date
    payment_method: str
    title: str
    description: str | None
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    category_name: str | None = None
    paid_by_name: str | None = None
    created_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseListResponse(BaseModel):
    """Paginated response containing list of expenses and summary statistics."""
    items: list[ExpenseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    total_amount: Decimal
