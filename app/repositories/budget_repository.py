from decimal import Decimal
import uuid
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Expense
from app.models.user import User


class BudgetRepository:
    """Data access repository for Budgets with SQL aggregation."""

    @staticmethod
    def _build_spent_subquery():
        """Correlated scalar subquery calculating total expenses in SQL without loading rows into Python."""
        return (
            select(func.coalesce(func.sum(Expense.amount), Decimal("0.00")))
            .where(
                Expense.family_id == Budget.family_id,
                Expense.category_id == Budget.category_id,
                extract("year", Expense.expense_date) == Budget.year,
                extract("month", Expense.expense_date) == Budget.month,
            )
            .correlate(Budget)
            .scalar_subquery()
        )

    @classmethod
    def _build_select_query(cls):
        """Construct the base select query joining category, user, and spent subquery."""
        spent_subquery = cls._build_spent_subquery()
        return (
            select(
                Budget,
                Category.name.label("category_name"),
                Category.icon.label("category_icon"),
                Category.color.label("category_color"),
                User.full_name.label("created_by_name"),
                spent_subquery.label("amount_spent"),
            )
            .outerjoin(Category, Budget.category_id == Category.id)
            .outerjoin(User, Budget.created_by == User.id)
        )

    @staticmethod
    def compute_budget_fields(
        budget: Budget,
        category_name: str | None,
        category_icon: str | None,
        category_color: str | None,
        created_by_name: str | None,
        amount_spent: Decimal | None,
    ) -> dict:
        """Calculate spent, remaining, percentage used, and warning levels."""
        spent = Decimal(str(amount_spent or "0.00"))
        budget_amount = budget.amount
        remaining = budget_amount - spent

        if budget_amount > 0:
            pct = Decimal(str(round((spent / budget_amount) * 100, 2)))
        else:
            pct = Decimal("0.00")

        # Warnings thresholds: 75%, 90%, 100%+
        if pct >= 100:
            warning_level = "100%+"
        elif pct >= 90:
            warning_level = "90%"
        elif pct >= 75:
            warning_level = "75%"
        else:
            warning_level = "normal"

        return {
            "id": budget.id,
            "family_id": budget.family_id,
            "category_id": budget.category_id,
            "category_name": category_name,
            "category_icon": category_icon,
            "category_color": category_color,
            "month": budget.month,
            "year": budget.year,
            "amount": budget_amount,
            "amount_spent": spent,
            "remaining_amount": remaining,
            "percentage_used": pct,
            "warning_level": warning_level,
            "has_warning": pct >= 75,
            "is_exceeded": pct >= 100,
            "created_by": budget.created_by,
            "created_by_name": created_by_name,
            "created_at": budget.created_at,
            "updated_at": budget.updated_at,
        }

    @classmethod
    async def get_by_id(
        cls, session: AsyncSession, budget_id: uuid.UUID, family_id: uuid.UUID
    ) -> dict | None:
        """Retrieve single budget with SQL aggregation for the specified family."""
        query = (
            cls._build_select_query()
            .where(Budget.id == budget_id, Budget.family_id == family_id)
        )
        result = await session.execute(query)
        row = result.first()
        if not row:
            return None
        return cls.compute_budget_fields(
            budget=row.Budget,
            category_name=row.category_name,
            category_icon=row.category_icon,
            category_color=row.category_color,
            created_by_name=row.created_by_name,
            amount_spent=row.amount_spent,
        )

    @staticmethod
    async def get_model_by_id(
        session: AsyncSession, budget_id: uuid.UUID, family_id: uuid.UUID
    ) -> Budget | None:
        """Fetch the raw Budget ORM model instance for updates/deletions."""
        stmt = select(Budget).where(Budget.id == budget_id, Budget.family_id == family_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_unique(
        session: AsyncSession,
        family_id: uuid.UUID,
        category_id: uuid.UUID,
        month: int,
        year: int,
        exclude_id: uuid.UUID | None = None,
    ) -> Budget | None:
        """Find an existing budget for the same family, category, month, and year."""
        stmt = select(Budget).where(
            Budget.family_id == family_id,
            Budget.category_id == category_id,
            Budget.month == month,
            Budget.year == year,
        )
        if exclude_id is not None:
            stmt = stmt.where(Budget.id != exclude_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def list_for_family(
        cls,
        session: AsyncSession,
        family_id: uuid.UUID,
        month: int | None = None,
        year: int | None = None,
        category_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """Fetch all budgets for a family with SQL-aggregated spending."""
        query = cls._build_select_query().where(Budget.family_id == family_id)

        if month is not None:
            query = query.where(Budget.month == month)
        if year is not None:
            query = query.where(Budget.year == year)
        if category_id is not None:
            query = query.where(Budget.category_id == category_id)

        query = query.order_by(Budget.year.desc(), Budget.month.desc(), Category.name.asc())
        result = await session.execute(query)
        rows = result.all()

        return [
            cls.compute_budget_fields(
                budget=row.Budget,
                category_name=row.category_name,
                category_icon=row.category_icon,
                category_color=row.category_color,
                created_by_name=row.created_by_name,
                amount_spent=row.amount_spent,
            )
            for row in rows
        ]

    @staticmethod
    async def create(session: AsyncSession, budget: Budget) -> Budget:
        """Persist a new budget."""
        session.add(budget)
        await session.flush()
        await session.refresh(budget)
        return budget

    @staticmethod
    async def update(session: AsyncSession, budget: Budget) -> Budget:
        """Update an existing budget."""
        await session.flush()
        await session.refresh(budget)
        return budget

    @staticmethod
    async def delete(session: AsyncSession, budget: Budget) -> None:
        """Delete a budget."""
        await session.delete(budget)
        await session.flush()
