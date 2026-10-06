import calendar
from datetime import date
from decimal import Decimal
from typing import Any
import uuid
from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.family import FamilyMember
from app.models.relationship import FamilyRelationship
from app.models.transaction import Expense, Income
from app.models.user import User


def to_decimal_2(val: Any) -> Decimal:
    """Safely convert value to Decimal with exactly 2 decimal places."""
    if val is None:
        return Decimal("0.00")
    try:
        d = Decimal(str(val))
        return d.quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def resolve_date_range(
    from_date: date | None = None,
    to_date: date | None = None,
    month: int | None = None,
    year: int | None = None,
) -> tuple[date, date]:
    """
    Resolve start and end dates from provided parameters.
    1. from_date and to_date
    2. month and year
    3. year only
    4. Default: current month
    """
    today = date.today()

    if from_date and to_date:
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        return from_date, to_date

    if month is not None:
        y = year if year is not None else today.year
        _, last_day = calendar.monthrange(y, month)
        return date(y, month, 1), date(y, month, last_day)

    if year is not None:
        return date(year, 1, 1), date(year, 12, 31)

    # Default to current month
    _, last_day = calendar.monthrange(today.year, today.month)
    return date(today.year, today.month, 1), date(today.year, today.month, last_day)


class ReportRepository:
    """PostgreSQL aggregation repository for reports and dashboards."""

    @staticmethod
    async def get_dashboard_expense_aggregates(
        session: AsyncSession,
        family_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Decimal]:
        """
        Aggregate total expenses, shared vs personal, and my vs spouse expenses in a single SQL query.
        """
        stmt = (
            select(
                func.coalesce(func.sum(Expense.amount), Decimal("0.00")).label("total_expenses"),
                func.coalesce(
                    func.sum(case((Expense.is_shared.is_(True), Expense.amount), else_=Decimal("0.00"))),
                    Decimal("0.00"),
                ).label("shared_expenses"),
                func.coalesce(
                    func.sum(case((Expense.is_shared.is_(False), Expense.amount), else_=Decimal("0.00"))),
                    Decimal("0.00"),
                ).label("personal_expenses"),
                func.coalesce(
                    func.sum(case((Expense.paid_by == user_id, Expense.amount), else_=Decimal("0.00"))),
                    Decimal("0.00"),
                ).label("my_expenses"),
                func.coalesce(
                    func.sum(case((Expense.paid_by != user_id, Expense.amount), else_=Decimal("0.00"))),
                    Decimal("0.00"),
                ).label("spouse_expenses"),
            )
            .where(
                Expense.family_id == family_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )
        )
        row = (await session.execute(stmt)).one()
        return {
            "total_expenses": to_decimal_2(row.total_expenses),
            "shared_expenses": to_decimal_2(row.shared_expenses),
            "personal_expenses": to_decimal_2(row.personal_expenses),
            "my_expenses": to_decimal_2(row.my_expenses),
            "spouse_expenses": to_decimal_2(row.spouse_expenses),
        }

    @staticmethod
    async def get_total_income(
        session: AsyncSession,
        family_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Aggregate total income for the family in a date range."""
        stmt = (
            select(func.coalesce(func.sum(Income.amount), Decimal("0.00")).label("total_income"))
            .where(
                Income.family_id == family_id,
                Income.income_date >= start_date,
                Income.income_date <= end_date,
            )
        )
        result = (await session.execute(stmt)).scalar_one()
        return to_decimal_2(result)

    @staticmethod
    async def get_recent_transactions(
        session: AsyncSession,
        family_id: uuid.UUID,
        limit: int = 5,
    ) -> list[dict]:
        """Fetch the most recent transactions across expenses and incomes."""
        # 1. Fetch top expenses
        exp_stmt = (
            select(
                Expense.id,
                Expense.title,
                Expense.amount,
                Expense.currency,
                Expense.expense_date.label("date"),
                Expense.payment_method,
                Expense.is_shared,
                Expense.created_at,
                Category.name.label("category_name"),
                Category.icon.label("category_icon"),
                Category.color.label("category_color"),
                User.full_name.label("user_name"),
            )
            .outerjoin(Category, Expense.category_id == Category.id)
            .join(User, Expense.paid_by == User.id)
            .where(Expense.family_id == family_id)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .limit(limit)
        )
        exp_rows = (await session.execute(exp_stmt)).all()

        # 2. Fetch top incomes
        inc_stmt = (
            select(
                Income.id,
                Income.title,
                Income.amount,
                Income.currency,
                Income.income_date.label("date"),
                Income.created_at,
                Category.name.label("category_name"),
                Category.icon.label("category_icon"),
                Category.color.label("category_color"),
                User.full_name.label("user_name"),
            )
            .outerjoin(Category, Income.category_id == Category.id)
            .join(User, Income.user_id == User.id)
            .where(Income.family_id == family_id)
            .order_by(Income.income_date.desc(), Income.created_at.desc())
            .limit(limit)
        )
        inc_rows = (await session.execute(inc_stmt)).all()

        # 3. Combine and sort
        combined = []
        for r in exp_rows:
            combined.append({
                "id": r.id,
                "type": "expense",
                "title": r.title,
                "amount": to_decimal_2(r.amount),
                "currency": r.currency,
                "date": r.date,
                "category_name": r.category_name,
                "category_icon": r.category_icon,
                "category_color": r.category_color,
                "user_name": r.user_name,
                "is_shared": r.is_shared,
                "payment_method": r.payment_method,
                "created_at": r.created_at,
            })
        for r in inc_rows:
            combined.append({
                "id": r.id,
                "type": "income",
                "title": r.title,
                "amount": to_decimal_2(r.amount),
                "currency": r.currency,
                "date": r.date,
                "category_name": r.category_name,
                "category_icon": r.category_icon,
                "category_color": r.category_color,
                "user_name": r.user_name,
                "is_shared": None,
                "payment_method": None,
                "created_at": r.created_at,
            })

        combined.sort(key=lambda x: (x["date"], x["created_at"]), reverse=True)
        return combined[:limit]

    @staticmethod
    async def get_monthly_aggregates(
        session: AsyncSession,
        family_id: uuid.UUID,
        year: int,
    ) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
        """
        Aggregate expenses and incomes grouped by month for a given year using PostgreSQL EXTRACT and SUM.
        Returns ({month: expense_sum}, {month: income_sum}).
        """
        exp_stmt = (
            select(
                extract("month", Expense.expense_date).label("month"),
                func.coalesce(func.sum(Expense.amount), Decimal("0.00")).label("total"),
            )
            .where(
                Expense.family_id == family_id,
                extract("year", Expense.expense_date) == year,
            )
            .group_by("month")
        )
        exp_rows = (await session.execute(exp_stmt)).all()
        expense_map = {int(r.month): to_decimal_2(r.total) for r in exp_rows}

        inc_stmt = (
            select(
                extract("month", Income.income_date).label("month"),
                func.coalesce(func.sum(Income.amount), Decimal("0.00")).label("total"),
            )
            .where(
                Income.family_id == family_id,
                extract("year", Income.income_date) == year,
            )
            .group_by("month")
        )
        inc_rows = (await session.execute(inc_stmt)).all()
        income_map = {int(r.month): to_decimal_2(r.total) for r in inc_rows}

        return expense_map, income_map

    @staticmethod
    async def get_category_aggregates(
        session: AsyncSession,
        family_id: uuid.UUID,
        start_date: date,
        end_date: date,
        category_type: str = "expense",
    ) -> list[dict]:
        """
        Aggregate amounts by category with sum and transaction counts.
        """
        if category_type == "income":
            stmt = (
                select(
                    Category.id.label("category_id"),
                    func.coalesce(Category.name, "Uncategorized").label("category_name"),
                    Category.icon.label("category_icon"),
                    Category.color.label("category_color"),
                    func.coalesce(Category.type, "income").label("type"),
                    func.coalesce(func.sum(Income.amount), Decimal("0.00")).label("total_amount"),
                    func.count(Income.id).label("transaction_count"),
                )
                .select_from(Income)
                .outerjoin(Category, Income.category_id == Category.id)
                .where(
                    Income.family_id == family_id,
                    Income.income_date >= start_date,
                    Income.income_date <= end_date,
                )
                .group_by(Category.id, Category.name, Category.icon, Category.color, Category.type)
                .order_by(func.sum(Income.amount).desc())
            )
        else:
            stmt = (
                select(
                    Category.id.label("category_id"),
                    func.coalesce(Category.name, "Uncategorized").label("category_name"),
                    Category.icon.label("category_icon"),
                    Category.color.label("category_color"),
                    func.coalesce(Category.type, "expense").label("type"),
                    func.coalesce(func.sum(Expense.amount), Decimal("0.00")).label("total_amount"),
                    func.count(Expense.id).label("transaction_count"),
                )
                .select_from(Expense)
                .outerjoin(Category, Expense.category_id == Category.id)
                .where(
                    Expense.family_id == family_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date,
                )
                .group_by(Category.id, Category.name, Category.icon, Category.color, Category.type)
                .order_by(func.sum(Expense.amount).desc())
            )

        rows = (await session.execute(stmt)).all()
        return [
            {
                "category_id": r.category_id,
                "category_name": r.category_name,
                "category_icon": r.category_icon,
                "category_color": r.category_color,
                "type": r.type,
                "total_amount": to_decimal_2(r.total_amount),
                "transaction_count": r.transaction_count,
            }
            for r in rows
        ]

    @staticmethod
    async def get_member_aggregates(
        session: AsyncSession,
        family_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> tuple[list[dict], dict[str, Decimal]]:
        """
        Aggregate spending and income per family member ("Husband vs Wife" comparison).
        """
        # 1. Fetch active members of the family
        mem_stmt = (
            select(
                User.id.label("user_id"),
                User.full_name.label("user_name"),
                User.avatar_url,
                FamilyMember.role,
                FamilyMember.relationship,
            )
            .join(FamilyMember, FamilyMember.user_id == User.id)
            .where(
                FamilyMember.family_id == family_id,
                FamilyMember.status == "active",
            )
        )
        members = (await session.execute(mem_stmt)).all()

        # 2. Aggregate expenses paid by each member
        exp_stmt = (
            select(
                Expense.paid_by.label("user_id"),
                func.coalesce(func.sum(Expense.amount), Decimal("0.00")).label("total_paid"),
                func.coalesce(
                    func.sum(case((Expense.is_shared.is_(True), Expense.amount), else_=Decimal("0.00"))),
                    Decimal("0.00"),
                ).label("shared_expenses"),
                func.coalesce(
                    func.sum(case((Expense.is_shared.is_(False), Expense.amount), else_=Decimal("0.00"))),
                    Decimal("0.00"),
                ).label("personal_expenses"),
            )
            .where(
                Expense.family_id == family_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )
            .group_by(Expense.paid_by)
        )
        exp_rows = {r.user_id: r for r in (await session.execute(exp_stmt)).all()}

        # 3. Aggregate income received by each member
        inc_stmt = (
            select(
                Income.user_id,
                func.coalesce(func.sum(Income.amount), Decimal("0.00")).label("income_earned"),
            )
            .where(
                Income.family_id == family_id,
                Income.income_date >= start_date,
                Income.income_date <= end_date,
            )
            .group_by(Income.user_id)
        )
        inc_rows = {r.user_id: r for r in (await session.execute(inc_stmt)).all()}

        # 4. Overall totals
        total_expenses = sum((r.total_paid for r in exp_rows.values()), Decimal("0.00"))
        total_income = sum((r.income_earned for r in inc_rows.values()), Decimal("0.00"))
        shared_expenses = sum((r.shared_expenses for r in exp_rows.values()), Decimal("0.00"))
        personal_expenses = sum((r.personal_expenses for r in exp_rows.values()), Decimal("0.00"))

        member_items = []
        for m in members:
            exp_data = exp_rows.get(m.user_id)
            inc_data = inc_rows.get(m.user_id)

            paid = to_decimal_2(exp_data.total_paid if exp_data else Decimal("0.00"))
            shared = to_decimal_2(exp_data.shared_expenses if exp_data else Decimal("0.00"))
            personal = to_decimal_2(exp_data.personal_expenses if exp_data else Decimal("0.00"))
            earned = to_decimal_2(inc_data.income_earned if inc_data else Decimal("0.00"))

            pct = (
                to_decimal_2((paid / total_expenses) * Decimal("100"))
                if total_expenses > 0
                else Decimal("0.00")
            )

            rel = getattr(m, "relationship", "other") or "other"
            member_items.append({
                "user_id": m.user_id,
                "user_name": m.user_name,
                "avatar_url": m.avatar_url,
                "role": m.role,
                "relationship": rel,
                "relationship_label": FamilyRelationship.get_relationship_label(rel),
                "total_paid": paid,
                "percentage_of_total": pct,
                "personal_expenses": personal,
                "shared_expenses": shared,
                "income_earned": earned,
            })

        totals = {
            "total_expenses": to_decimal_2(total_expenses),
            "total_income": to_decimal_2(total_income),
            "shared_expenses": to_decimal_2(shared_expenses),
            "personal_expenses": to_decimal_2(personal_expenses),
        }
        return member_items, totals

    @staticmethod
    async def get_payment_method_aggregates(
        session: AsyncSession,
        family_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Aggregate expenses by payment method."""
        stmt = (
            select(
                Expense.payment_method,
                func.coalesce(func.sum(Expense.amount), Decimal("0.00")).label("total_amount"),
                func.count(Expense.id).label("transaction_count"),
            )
            .where(
                Expense.family_id == family_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )
            .group_by(Expense.payment_method)
            .order_by(func.sum(Expense.amount).desc())
        )
        rows = (await session.execute(stmt)).all()
        return [
            {
                "payment_method": r.payment_method,
                "total_amount": to_decimal_2(r.total_amount),
                "transaction_count": r.transaction_count,
            }
            for r in rows
        ]
