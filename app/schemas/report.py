from datetime import date, datetime
from decimal import Decimal
from typing import Literal
import uuid
from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# Dashboard Schemas
# ==========================================

class DashboardDateRange(BaseModel):
    """Active date window used for dashboard computations."""
    from_date: date
    to_date: date
    month: int | None = None
    year: int | None = None


class DashboardBudgetSummary(BaseModel):
    """Consolidated budget usage indicators for the active period."""
    total_budget: Decimal
    total_spent: Decimal
    total_remaining: Decimal
    percentage_used: Decimal
    has_warning: bool
    is_exceeded: bool
    active_budgets_count: int
    budgets_exceeded_count: int


class DashboardTransactionItem(BaseModel):
    """Unified transaction item (expense or income) for recent transaction feeds."""
    id: uuid.UUID
    type: Literal["expense", "income"]
    title: str
    amount: Decimal
    currency: str
    date: date
    category_name: str | None = None
    category_icon: str | None = None
    category_color: str | None = None
    user_name: str
    is_shared: bool | None = None
    payment_method: str | None = None
    created_at: datetime


class DashboardResponse(BaseModel):
    """Primary dashboard summary payload for Flutter home view."""
    period: DashboardDateRange
    currency: str
    total_income: Decimal
    total_expenses: Decimal
    remaining_balance: Decimal
    savings_rate: Decimal  # (remaining_balance / total_income) * 100
    shared_expenses: Decimal
    personal_expenses: Decimal
    my_expenses: Decimal
    spouse_expenses: Decimal
    budget_status: DashboardBudgetSummary
    recent_transactions: list[DashboardTransactionItem]

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Monthly Report Schemas
# ==========================================

class MonthlyReportItem(BaseModel):
    """Monthly financial performance record."""
    month: int
    month_name: str
    year: int
    income: Decimal
    expenses: Decimal
    net_savings: Decimal
    savings_rate: Decimal


class MonthlyReportResponse(BaseModel):
    """Annual monthly breakdown report."""
    year: int
    currency: str
    total_income: Decimal
    total_expenses: Decimal
    net_savings: Decimal
    overall_savings_rate: Decimal
    months: list[MonthlyReportItem]

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Category Report Schemas
# ==========================================

class CategoryReportItem(BaseModel):
    """Category spending or income breakdown item."""
    category_id: uuid.UUID | None
    category_name: str
    category_icon: str | None = None
    category_color: str | None = None
    type: str  # "expense" or "income"
    amount: Decimal
    percentage: Decimal  # % of total amount for this type
    transaction_count: int


class CategoryReportResponse(BaseModel):
    """Category distribution report payload."""
    from_date: date
    to_date: date
    currency: str
    type: str  # "expense" or "income"
    total_amount: Decimal
    categories: list[CategoryReportItem]

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Member Report Schemas (Husband vs Wife)
# ==========================================

class MemberReportItem(BaseModel):
    """Individual family member's spending and income contributions."""
    user_id: uuid.UUID
    user_name: str
    avatar_url: str | None = None
    role: str
    relationship: str = "other"
    relationship_label: str = "Other"
    total_paid: Decimal
    percentage_of_total: Decimal
    personal_expenses: Decimal
    shared_expenses: Decimal
    income_earned: Decimal


class MemberReportResponse(BaseModel):
    """Member comparison report ("Husband vs Wife" spending)."""
    from_date: date
    to_date: date
    currency: str
    total_expenses: Decimal
    total_income: Decimal
    shared_expenses: Decimal
    personal_expenses: Decimal
    members: list[MemberReportItem]

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Payment Method Report Schemas
# ==========================================

class PaymentMethodReportItem(BaseModel):
    """Spending breakdown by payment instrument."""
    payment_method: str
    amount: Decimal
    percentage: Decimal
    transaction_count: int


class PaymentMethodReportResponse(BaseModel):
    """Payment method distribution report."""
    from_date: date
    to_date: date
    currency: str
    total_amount: Decimal
    payment_methods: list[PaymentMethodReportItem]

    model_config = ConfigDict(from_attributes=True)
