from datetime import date
from decimal import Decimal
import uuid
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.category import Category
from app.models.transaction import Expense
from app.models.user import User


class ExpenseRepository:
    """Data access repository for Expense entities with strict family-level isolation."""

    @staticmethod
    async def get_by_id_and_family(
        session: AsyncSession, expense_id: uuid.UUID, family_id: uuid.UUID
    ) -> tuple[Expense, str, str, str] | None:
        """
        Fetch a single expense by ID, strictly enforcing family isolation.
        Returns (Expense, category_name, paid_by_name, created_by_name).
        """
        creator_alias = aliased(User)
        payer_alias = aliased(User)

        stmt = (
            select(
                Expense,
                Category.name.label("category_name"),
                payer_alias.full_name.label("paid_by_name"),
                creator_alias.full_name.label("created_by_name"),
            )
            .join(Category, Expense.category_id == Category.id)
            .join(payer_alias, Expense.paid_by == payer_alias.id)
            .join(creator_alias, Expense.created_by == creator_alias.id)
            .where(Expense.id == expense_id, Expense.family_id == family_id)
        )
        result = await session.execute(stmt)
        row = result.first()
        if not row:
            return None
        return row[0], row[1], row[2], row[3]

    @staticmethod
    async def create(session: AsyncSession, expense: Expense) -> Expense:
        """Persist a new Expense record."""
        session.add(expense)
        await session.flush()
        await session.refresh(expense)
        return expense

    @staticmethod
    async def update(session: AsyncSession, expense: Expense) -> Expense:
        """Update an existing Expense record."""
        await session.flush()
        await session.refresh(expense)
        return expense

    @staticmethod
    async def delete(session: AsyncSession, expense: Expense) -> None:
        """Delete an expense record."""
        await session.delete(expense)
        await session.flush()

    @staticmethod
    async def list_expenses(
        session: AsyncSession,
        family_id: uuid.UUID,
        search: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        category_id: uuid.UUID | None = None,
        paid_by: uuid.UUID | None = None,
        payment_method: str | None = None,
        is_shared: bool | None = None,
        sort_by: str = "expense_date",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[Expense, str, str, str]], int, Decimal]:
        """
        Filter, search, sort, and paginate expenses strictly within the given family.
        Returns:
            (items_with_names, total_records_count, total_sum_amount)
        """
        creator_alias = aliased(User)
        payer_alias = aliased(User)

        # Base filter condition strictly isolating by family_id
        filters = [Expense.family_id == family_id]

        if search:
            search_pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Expense.title.ilike(search_pattern),
                    Expense.description.ilike(search_pattern),
                )
            )

        if from_date:
            filters.append(Expense.expense_date >= from_date)

        if to_date:
            filters.append(Expense.expense_date <= to_date)

        if category_id:
            filters.append(Expense.category_id == category_id)

        if paid_by:
            filters.append(Expense.paid_by == paid_by)

        if payment_method:
            filters.append(Expense.payment_method == payment_method.strip().lower())

        if is_shared is not None:
            filters.append(Expense.is_shared.is_(is_shared))

        # 1. Total count query
        count_stmt = select(func.count(Expense.id)).where(*filters)
        total_count = (await session.execute(count_stmt)).scalar() or 0

        # 2. Total amount sum query
        sum_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(*filters)
        total_amount = (await session.execute(sum_stmt)).scalar() or Decimal("0.00")

        # 3. Dynamic sorting
        sort_columns: dict[str, Any] = {
            "expense_date": Expense.expense_date,
            "amount": Expense.amount,
            "created_at": Expense.created_at,
            "title": Expense.title,
        }
        sort_col = sort_columns.get(sort_by, Expense.expense_date)
        order_expression = sort_col.desc() if sort_order.lower() == "desc" else sort_col.asc()

        # Secondary sort by id for deterministic pagination
        items_stmt = (
            select(
                Expense,
                Category.name.label("category_name"),
                payer_alias.full_name.label("paid_by_name"),
                creator_alias.full_name.label("created_by_name"),
            )
            .join(Category, Expense.category_id == Category.id)
            .join(payer_alias, Expense.paid_by == payer_alias.id)
            .join(creator_alias, Expense.created_by == creator_alias.id)
            .where(*filters)
            .order_by(order_expression, Expense.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = (await session.execute(items_stmt)).all()
        result_items = [(row[0], row[1], row[2], row[3]) for row in items]

        return result_items, total_count, total_amount
