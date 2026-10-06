from datetime import date
import uuid
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.income import (
    IncomeCreateRequest,
    IncomeListResponse,
    IncomeResponse,
    IncomeUpdateRequest,
)
from app.services.income_service import IncomeService

router = APIRouter(prefix="/income", tags=["Income"])


@router.get(
    "",
    response_model=IncomeListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Income with Filters & Pagination",
    description="Retrieve paginated income entries for the user's family with date, category, and person filtering.",
)
async def list_income(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    from_date: date | None = Query(default=None, description="Filter income received on or after this date"),
    to_date: date | None = Query(default=None, description="Filter income received on or before this date"),
    category_id: uuid.UUID | None = Query(default=None, description="Filter by category ID"),
    received_by: uuid.UUID | None = Query(default=None, description="Filter by recipient member user ID"),
    sort_by: str = Query(default="income_date", pattern="^(income_date|amount|created_at|title)$", description="Field to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order: asc or desc"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List family income entries."""
    return await IncomeService.list_income(
        session=db,
        user=current_user,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
        category_id=category_id,
        received_by=received_by,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post(
    "",
    response_model=IncomeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Income",
    description="Record a new income entry for the authenticated user's family.",
)
async def create_income(
    data: IncomeCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new income entry."""
    return await IncomeService.create_income(db, current_user, data)


@router.get(
    "/{income_id}",
    response_model=IncomeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Income Details",
    description="Fetch a specific income record by ID. Strictly limited to the user's family.",
)
async def get_income(
    income_id: uuid.UUID = Path(..., description="ID of the income record to retrieve"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve single income details."""
    return await IncomeService.get_income(db, current_user, income_id)


@router.put(
    "/{income_id}",
    response_model=IncomeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Income",
    description="Update an existing income record within the user's family.",
)
async def update_income(
    data: IncomeUpdateRequest,
    income_id: uuid.UUID = Path(..., description="ID of the income record to update"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update income details."""
    return await IncomeService.update_income(db, current_user, income_id, data)


@router.delete(
    "/{income_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Income",
    description="Permanently delete an income entry belonging to the user's family.",
)
async def delete_income(
    income_id: uuid.UUID = Path(..., description="ID of the income record to delete"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an income entry."""
    await IncomeService.delete_income(db, current_user, income_id)
    return MessageResponse(message="Income successfully deleted.")
