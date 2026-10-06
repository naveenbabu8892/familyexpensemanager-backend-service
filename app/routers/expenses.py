from datetime import date
import uuid
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.expense import (
    ExpenseCreateRequest,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseUpdateRequest,
)
from app.services.expense_service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.get(
    "",
    response_model=ExpenseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Expenses with Filters & Pagination",
    description="Retrieve paginated expenses for the authenticated user's family with filtering, searching, and sorting.",
)
async def list_expenses(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(default=None, description="Search term matching title or description"),
    from_date: date | None = Query(default=None, description="Filter expenses on or after this date"),
    to_date: date | None = Query(default=None, description="Filter expenses on or before this date"),
    category_id: uuid.UUID | None = Query(default=None, description="Filter by category ID"),
    paid_by: uuid.UUID | None = Query(default=None, description="Filter by payer user ID"),
    payment_method: str | None = Query(default=None, description="Filter by payment method"),
    is_shared: bool | None = Query(default=None, description="Filter by shared vs personal status"),
    sort_by: str = Query(default="expense_date", pattern="^(expense_date|amount|created_at|title)$", description="Field to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order: asc or desc"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List family expenses with extensive filters."""
    return await ExpenseService.list_expenses(
        session=db,
        user=current_user,
        page=page,
        page_size=page_size,
        search=search,
        from_date=from_date,
        to_date=to_date,
        category_id=category_id,
        paid_by=paid_by,
        payment_method=payment_method,
        is_shared=is_shared,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post(
    "",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Expense",
    description="Record a new expense for the authenticated user's family.",
)
async def create_expense(
    data: ExpenseCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new expense."""
    return await ExpenseService.create_expense(db, current_user, data)


@router.get(
    "/{expense_id}",
    response_model=ExpenseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Expense Details",
    description="Fetch a specific expense by ID. Strictly limited to the user's family.",
)
async def get_expense(
    expense_id: uuid.UUID = Path(..., description="ID of the expense to retrieve"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve single expense details."""
    return await ExpenseService.get_expense(db, current_user, expense_id)


@router.put(
    "/{expense_id}",
    response_model=ExpenseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Expense",
    description="Update an existing expense within the user's family.",
)
async def update_expense(
    data: ExpenseUpdateRequest,
    expense_id: uuid.UUID = Path(..., description="ID of the expense to update"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update expense details."""
    return await ExpenseService.update_expense(db, current_user, expense_id, data)


@router.delete(
    "/{expense_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Expense",
    description="Permanently delete an expense belonging to the user's family.",
)
async def delete_expense(
    expense_id: uuid.UUID = Path(..., description="ID of the expense to delete"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an expense record."""
    await ExpenseService.delete_expense(db, current_user, expense_id)
    return MessageResponse(message="Expense successfully deleted.")
