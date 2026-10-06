from datetime import date
from decimal import Decimal
import uuid
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Income
from app.models.user import User


class IncomeRepository:
    """Data access repository for Income entities with family isolation."""

    @staticmethod
    async def get_by_id_and_family(
        session: AsyncSession, income_id: uuid.UUID, family_id: uuid.UUID
    ) -> tuple[Income, str | None, str] | None:
        """
        Fetch a single income by ID, strictly enforcing family isolation.
        Returns (Income, category_name, received_by_name).
        """
        stmt = (
            select(
                Income,
                Category.name.label("category_name"),
                User.full_name.label("received_by_name"),
            )
            .outerjoin(Category, Income.category_id == Category.id)
            .join(User, Income.user_id == User.id)
            .where(Income.id == income_id, Income.family_id == family_id)
        )
        result = await session.execute(stmt)
        row = result.first()
        if not row:
            return None
        return row[0], row[1], row[2]

    @staticmethod
    async def create(session: AsyncSession, income: Income) -> Income:
        """Persist a new Income record."""
        session.add(income)
        await session.flush()
        await session.refresh(income)
        return income

    @staticmethod
    async def update(session: AsyncSession, income: Income) -> Income:
        """Update an existing Income record."""
        await session.flush()
        await session.refresh(income)
        return income

    @staticmethod
    async def delete(session: AsyncSession, income: Income) -> None:
        """Delete an Income record."""
        await session.delete(income)
        await session.flush()

    @staticmethod
    async def list_income(
        session: AsyncSession,
        family_id: uuid.UUID,
        from_date: date | None = None,
        to_date: date | None = None,
        category_id: uuid.UUID | None = None,
        received_by: uuid.UUID | None = None,
        sort_by: str = "income_date",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[Income, str | None, str]], int, Decimal]:
        """
        Filter, sort, and paginate income records within the family.
        Returns:
            (items_with_names, total_records_count, total_sum_amount)
        """
        filters = [Income.family_id == family_id]

        if from_date:
            filters.append(Income.income_date >= from_date)

        if to_date:
            filters.append(Income.income_date <= to_date)

        if category_id:
            filters.append(Income.category_id == category_id)

        if received_by:
            filters.append(Income.user_id == received_by)

        # 1. Total count query
        count_stmt = select(func.count(Income.id)).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar() or 0

        # 2. Total amount sum query
        sum_stmt = select(func.coalesce(func.sum(Income.amount), Decimal("0.00"))).where(*filters)
        total_amount = (await session.execute(sum_stmt)).scalar() or Decimal("0.00")

        # 3. Dynamic sorting
        sort_columns: dict[str, Any] = {
            "income_date": Income.income_date,
            "amount": Income.amount,
            "created_at": Income.created_at,
            "title": Income.title,
        }
        sort_col = sort_columns.get(sort_by, Income.income_date)
        order_expression = sort_col.desc() if sort_order.lower() == "desc" else sort_col.asc()

        items_stmt = (
            select(
                Income,
                Category.name.label("category_name"),
                User.full_name.label("received_by_name"),
            )
            .outerjoin(Category, Income.category_id == Category.id)
            .join(User, Income.user_id == User.id)
            .where(*filters)
            .order_by(order_expression, Income.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = (await session.execute(items_stmt)).all()
        result_items = [(row[0], row[1], row[2]) for row in items]

        return result_items, total_count, total_amount
