import calendar
from datetime import date
from decimal import Decimal
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import Family
from app.models.user import User
from app.repositories.budget_repository import BudgetRepository
from app.repositories.report_repository import (
    ReportRepository,
    resolve_date_range,
    to_decimal_2,
)
from app.schemas.report import (
    CategoryReportItem,
    CategoryReportResponse,
    DashboardBudgetSummary,
    DashboardDateRange,
    DashboardResponse,
    DashboardTransactionItem,
    MemberReportItem,
    MemberReportResponse,
    MonthlyReportItem,
    MonthlyReportResponse,
    PaymentMethodReportItem,
    PaymentMethodReportResponse,
)


class ReportService:
    """Business logic for financial reporting and dashboard metrics."""

    @staticmethod
    async def get_dashboard(
        session: AsyncSession,
        family: Family,
        current_user: User,
        from_date: date | None = None,
        to_date: date | None = None,
        month: int | None = None,
        year: int | None = None,
    ) -> DashboardResponse:
        """
        Assemble unified dashboard summary with PostgreSQL aggregation.
        """
        start_date, end_date = resolve_date_range(from_date, to_date, month, year)

        # 1. Aggregated expenses (my, spouse, shared, personal, total)
        exp_stats = await ReportRepository.get_dashboard_expense_aggregates(
            session=session,
            family_id=family.id,
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
        )

        # 2. Aggregated total income
        total_income = await ReportRepository.get_total_income(
            session=session,
            family_id=family.id,
            start_date=start_date,
            end_date=end_date,
        )

        # 3. Balance and savings rate
        total_expenses = exp_stats["total_expenses"]
        remaining_balance = to_decimal_2(total_income - total_expenses)
        if total_income > 0:
            savings_rate = to_decimal_2((remaining_balance / total_income) * Decimal("100"))
        else:
            savings_rate = Decimal("0.00")

        # 4. Budget Status for the month/year
        budget_month = month or start_date.month
        budget_year = year or start_date.year
        budgets = await BudgetRepository.list_for_family(
            session=session,
            family_id=family.id,
            month=budget_month,
            year=budget_year,
        )

        total_budget = sum((b["amount"] for b in budgets), Decimal("0.00"))
        total_budget_spent = sum((b["amount_spent"] for b in budgets), Decimal("0.00"))
        total_budget_remaining = to_decimal_2(total_budget - total_budget_spent)
        if total_budget > 0:
            budget_pct = to_decimal_2((total_budget_spent / total_budget) * Decimal("100"))
        else:
            budget_pct = Decimal("0.00")

        budget_summary = DashboardBudgetSummary(
            total_budget=to_decimal_2(total_budget),
            total_spent=to_decimal_2(total_budget_spent),
            total_remaining=total_budget_remaining,
            percentage_used=budget_pct,
            has_warning=budget_pct >= 75,
            is_exceeded=budget_pct >= 100,
            active_budgets_count=len(budgets),
            budgets_exceeded_count=sum(1 for b in budgets if b["is_exceeded"]),
        )

        # 5. Recent transactions
        recent_txs = await ReportRepository.get_recent_transactions(
            session=session,
            family_id=family.id,
            limit=5,
        )

        return DashboardResponse(
            period=DashboardDateRange(
                from_date=start_date,
                to_date=end_date,
                month=month,
                year=year,
            ),
            currency=family.currency,
            total_income=total_income,
            total_expenses=total_expenses,
            remaining_balance=remaining_balance,
            savings_rate=savings_rate,
            shared_expenses=exp_stats["shared_expenses"],
            personal_expenses=exp_stats["personal_expenses"],
            my_expenses=exp_stats["my_expenses"],
            spouse_expenses=exp_stats["spouse_expenses"],
            budget_status=budget_summary,
            recent_transactions=[DashboardTransactionItem(**t) for t in recent_txs],
        )

    @staticmethod
    async def get_monthly_report(
        session: AsyncSession,
        family: Family,
        year: int | None = None,
    ) -> MonthlyReportResponse:
        """
        Generate annual month-by-month financial report.
        """
        target_year = year or date.today().year
        exp_map, inc_map = await ReportRepository.get_monthly_aggregates(
            session=session,
            family_id=family.id,
            year=target_year,
        )

        months_data = []
        cum_income = Decimal("0.00")
        cum_expenses = Decimal("0.00")

        for m in range(1, 13):
            inc = inc_map.get(m, Decimal("0.00"))
            exp = exp_map.get(m, Decimal("0.00"))
            savings = to_decimal_2(inc - exp)
            rate = to_decimal_2((savings / inc) * Decimal("100")) if inc > 0 else Decimal("0.00")

            cum_income += inc
            cum_expenses += exp

            months_data.append(
                MonthlyReportItem(
                    month=m,
                    month_name=calendar.month_name[m],
                    year=target_year,
                    income=inc,
                    expenses=exp,
                    net_savings=savings,
                    savings_rate=rate,
                )
            )

        cum_savings = to_decimal_2(cum_income - cum_expenses)
        overall_rate = (
            to_decimal_2((cum_savings / cum_income) * Decimal("100"))
            if cum_income > 0
            else Decimal("0.00")
        )

        return MonthlyReportResponse(
            year=target_year,
            currency=family.currency,
            total_income=to_decimal_2(cum_income),
            total_expenses=to_decimal_2(cum_expenses),
            net_savings=cum_savings,
            overall_savings_rate=overall_rate,
            months=months_data,
        )

    @staticmethod
    async def get_category_report(
        session: AsyncSession,
        family: Family,
        from_date: date | None = None,
        to_date: date | None = None,
        month: int | None = None,
        year: int | None = None,
        category_type: str = "expense",
    ) -> CategoryReportResponse:
        """
        Generate category breakdown report with percentage contributions.
        """
        start_date, end_date = resolve_date_range(from_date, to_date, month, year)
        normalized_type = category_type.lower().strip() if category_type else "expense"
        if normalized_type not in ("expense", "income"):
            normalized_type = "expense"

        cat_rows = await ReportRepository.get_category_aggregates(
            session=session,
            family_id=family.id,
            start_date=start_date,
            end_date=end_date,
            category_type=normalized_type,
        )

        total_amount = sum((r["total_amount"] for r in cat_rows), Decimal("0.00"))
        items = []
        for r in cat_rows:
            amt = r["total_amount"]
            pct = (
                to_decimal_2((amt / total_amount) * Decimal("100"))
                if total_amount > 0
                else Decimal("0.00")
            )
            items.append(
                CategoryReportItem(
                    category_id=r["category_id"],
                    category_name=r["category_name"],
                    category_icon=r["category_icon"],
                    category_color=r["category_color"],
                    type=r["type"],
                    amount=amt,
                    percentage=pct,
                    transaction_count=r["transaction_count"],
                )
            )

        return CategoryReportResponse(
            from_date=start_date,
            to_date=end_date,
            currency=family.currency,
            type=normalized_type,
            total_amount=to_decimal_2(total_amount),
            categories=items,
        )

    @staticmethod
    async def get_member_report(
        session: AsyncSession,
        family: Family,
        from_date: date | None = None,
        to_date: date | None = None,
        month: int | None = None,
        year: int | None = None,
    ) -> MemberReportResponse:
        """
        Generate member breakdown report ("Husband vs Wife" comparison).
        """
        start_date, end_date = resolve_date_range(from_date, to_date, month, year)
        member_items, totals = await ReportRepository.get_member_aggregates(
            session=session,
            family_id=family.id,
            start_date=start_date,
            end_date=end_date,
        )

        return MemberReportResponse(
            from_date=start_date,
            to_date=end_date,
            currency=family.currency,
            total_expenses=totals["total_expenses"],
            total_income=totals["total_income"],
            shared_expenses=totals["shared_expenses"],
            personal_expenses=totals["personal_expenses"],
            members=[MemberReportItem(**m) for m in member_items],
        )

    @staticmethod
    async def get_payment_method_report(
        session: AsyncSession,
        family: Family,
        from_date: date | None = None,
        to_date: date | None = None,
        month: int | None = None,
        year: int | None = None,
    ) -> PaymentMethodReportResponse:
        """
        Generate payment method distribution report.
        """
        start_date, end_date = resolve_date_range(from_date, to_date, month, year)
        method_rows = await ReportRepository.get_payment_method_aggregates(
            session=session,
            family_id=family.id,
            start_date=start_date,
            end_date=end_date,
        )

        total_amount = sum((r["total_amount"] for r in method_rows), Decimal("0.00"))
        items = []
        for r in method_rows:
            amt = r["total_amount"]
            pct = (
                to_decimal_2((amt / total_amount) * Decimal("100"))
                if total_amount > 0
                else Decimal("0.00")
            )
            items.append(
                PaymentMethodReportItem(
                    payment_method=r["payment_method"],
                    amount=amt,
                    percentage=pct,
                    transaction_count=r["transaction_count"],
                )
            )

        return PaymentMethodReportResponse(
            from_date=start_date,
            to_date=end_date,
            currency=family.currency,
            total_amount=to_decimal_2(total_amount),
            payment_methods=items,
        )
