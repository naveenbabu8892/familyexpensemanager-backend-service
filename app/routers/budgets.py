import uuid
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.family import get_current_family_context
from app.models.family import Family, FamilyMember
from app.models.user import User
from app.schemas.budget import (
    BudgetCreateRequest,
    BudgetDeleteResponse,
    BudgetResponse,
    BudgetUpdateRequest,
)
from app.services.budget_service import BudgetService

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.get(
    "",
    response_model=list[BudgetResponse],
    status_code=status.HTTP_200_OK,
    summary="List Family Budgets",
    description="List all monthly category budgets for the authenticated user's family with SQL-aggregated spending calculations and warning alerts.",
)
async def list_budgets(
    month: int | None = Query(default=None, ge=1, le=12, description="Filter by calendar month (1-12)"),
    year: int | None = Query(default=None, ge=2000, description="Filter by calendar year (>= 2000)"),
    category_id: uuid.UUID | None = Query(default=None, description="Filter by category UUID"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve family budgets with SQL aggregation."""
    family, _ = family_ctx
    return await BudgetService.list_budgets(
        session=db,
        family_id=family.id,
        month=month,
        year=year,
        category_id=category_id,
    )


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Monthly Budget",
    description="Create a new monthly category budget for the family.",
)
async def create_budget(
    data: BudgetCreateRequest,
    current_user: User = Depends(get_current_active_user),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Create a new budget."""
    family, _ = family_ctx
    return await BudgetService.create_budget(
        session=db,
        user=current_user,
        family_id=family.id,
        data=data,
    )


@router.get(
    "/{id}",
    response_model=BudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Budget Details",
    description="Retrieve a specific budget with up-to-date SQL spending and warning calculations.",
)
async def get_budget(
    id: uuid.UUID = Path(..., description="Unique UUID of the budget"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Fetch budget details by ID."""
    family, _ = family_ctx
    return await BudgetService.get_budget(session=db, family_id=family.id, budget_id=id)


@router.put(
    "/{id}",
    response_model=BudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Budget",
    description="Update an existing monthly budget allocation.",
)
async def update_budget(
    id: uuid.UUID = Path(..., description="Unique UUID of the budget to update"),
    data: BudgetUpdateRequest = ...,
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing budget."""
    family, _ = family_ctx
    return await BudgetService.update_budget(
        session=db,
        family_id=family.id,
        budget_id=id,
        data=data,
    )


@router.delete(
    "/{id}",
    response_model=BudgetDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Budget",
    description="Delete a monthly budget allocation.",
)
async def delete_budget(
    id: uuid.UUID = Path(..., description="Unique UUID of the budget to delete"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Delete a budget."""
    family, _ = family_ctx
    return await BudgetService.delete_budget(session=db, family_id=family.id, budget_id=id)
