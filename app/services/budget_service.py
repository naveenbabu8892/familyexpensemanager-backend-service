import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.models.user import User
from app.repositories.budget_repository import BudgetRepository
from app.repositories.category_repository import CategoryRepository
from app.schemas.budget import (
    BudgetCreateRequest,
    BudgetDeleteResponse,
    BudgetResponse,
    BudgetUpdateRequest,
)


class BudgetService:
    """Business logic for monthly category budgets."""

    @staticmethod
    async def list_budgets(
        session: AsyncSession,
        family_id: uuid.UUID,
        month: int | None = None,
        year: int | None = None,
        category_id: uuid.UUID | None = None,
    ) -> list[BudgetResponse]:
        """
        List all budgets for the family with SQL-aggregated spending.
        """
        if month is not None and not (1 <= month <= 12):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Month must be between 1 and 12.",
            )
        if year is not None and year < 2000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Year must be 2000 or later.",
            )

        budget_dicts = await BudgetRepository.list_for_family(
            session=session,
            family_id=family_id,
            month=month,
            year=year,
            category_id=category_id,
        )
        return [BudgetResponse(**b) for b in budget_dicts]

    @staticmethod
    async def get_budget(
        session: AsyncSession, family_id: uuid.UUID, budget_id: uuid.UUID
    ) -> BudgetResponse:
        """
        Retrieve a single budget by ID.
        Ensures strict family isolation.
        """
        budget_dict = await BudgetRepository.get_by_id(session, budget_id, family_id)
        if not budget_dict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found.",
            )
        return BudgetResponse(**budget_dict)

    @staticmethod
    async def create_budget(
        session: AsyncSession,
        user: User,
        family_id: uuid.UUID,
        data: BudgetCreateRequest,
    ) -> BudgetResponse:
        """
        Create a new monthly category budget.
        Rules:
        - Category must belong to the family or be an accessible system default.
        - Category must be an expense category.
        - One budget per family/category/month/year (409 Conflict).
        - Amount must be greater than zero.
        """
        if data.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Budget amount must be greater than zero.",
            )

        # Validate category accessibility
        category = await CategoryRepository.get_accessible_category(
            session, data.category_id, family_id
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found or does not belong to your family.",
            )

        # Ensure category is suitable for expenses
        if category.type not in ("expense", "both"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{category.name}' is an income category. Budgets can only be set for expense categories.",
            )

        # Enforce uniqueness: One budget per family/category/month/year
        existing = await BudgetRepository.get_by_unique(
            session=session,
            family_id=family_id,
            category_id=data.category_id,
            month=data.month,
            year=data.year,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A budget for category '{category.name}' in {data.month}/{data.year} already exists.",
            )

        budget = Budget(
            id=uuid.uuid4(),
            family_id=family_id,
            category_id=data.category_id,
            amount=data.amount,
            month=data.month,
            year=data.year,
            created_by=user.id,
        )
        created = await BudgetRepository.create(session, budget)

        # Retrieve with SQL aggregation
        return await BudgetService.get_budget(session, family_id, created.id)

    @staticmethod
    async def update_budget(
        session: AsyncSession,
        family_id: uuid.UUID,
        budget_id: uuid.UUID,
        data: BudgetUpdateRequest,
    ) -> BudgetResponse:
        """
        Update an existing budget.
        Rules:
        - Must belong to the family.
        - Re-checks category validity and expense type if updated.
        - Re-checks uniqueness if category, month, or year changes.
        """
        budget = await BudgetRepository.get_model_by_id(session, budget_id, family_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found.",
            )

        target_category_id = data.category_id if data.category_id is not None else budget.category_id
        target_month = data.month if data.month is not None else budget.month
        target_year = data.year if data.year is not None else budget.year

        # Validate category if changed
        if data.category_id is not None and data.category_id != budget.category_id:
            category = await CategoryRepository.get_accessible_category(
                session, data.category_id, family_id
            )
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category not found or does not belong to your family.",
                )
            if category.type not in ("expense", "both"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Category '{category.name}' is an income category. Budgets can only be set for expense categories.",
                )

        # Check uniqueness if category, month, or year changed
        if (
            target_category_id != budget.category_id
            or target_month != budget.month
            or target_year != budget.year
        ):
            existing = await BudgetRepository.get_by_unique(
                session=session,
                family_id=family_id,
                category_id=target_category_id,
                month=target_month,
                year=target_year,
                exclude_id=budget.id,
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A budget for this category in {target_month}/{target_year} already exists.",
                )

        if data.amount is not None:
            if data.amount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Budget amount must be greater than zero.",
                )
            budget.amount = data.amount
        if data.category_id is not None:
            budget.category_id = data.category_id
        if data.month is not None:
            budget.month = data.month
        if data.year is not None:
            budget.year = data.year

        await BudgetRepository.update(session, budget)
        return await BudgetService.get_budget(session, family_id, budget.id)

    @staticmethod
    async def delete_budget(
        session: AsyncSession, family_id: uuid.UUID, budget_id: uuid.UUID
    ) -> BudgetDeleteResponse:
        """
        Delete a budget by ID.
        """
        budget = await BudgetRepository.get_model_by_id(session, budget_id, family_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found.",
            )

        await BudgetRepository.delete(session, budget)
        return BudgetDeleteResponse(
            message="Budget deleted successfully.",
            budget_id=budget_id,
        )
