from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.family import get_current_family_context
from app.models.family import Family, FamilyMember
from app.schemas.report import (
    CategoryReportResponse,
    MemberReportResponse,
    MonthlyReportResponse,
    PaymentMethodReportResponse,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/monthly",
    response_model=MonthlyReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Monthly Financial Report",
    description="Retrieve month-by-month financial performance report (income, expenses, net savings, savings rate) for a given year.",
)
async def get_monthly_report(
    year: int | None = Query(default=None, ge=2000, description="Calendar year (default current year)"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve annual month-by-month financial report."""
    family, _ = family_ctx
    return await ReportService.get_monthly_report(session=db, family=family, year=year)


@router.get(
    "/categories",
    response_model=CategoryReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Category Distribution Report",
    description="Retrieve category-wise spending or income breakdown with percentages and transaction counts.",
)
async def get_category_report(
    from_date: date | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    to_date: date | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    month: int | None = Query(default=None, ge=1, le=12, description="Month filter (1-12)"),
    year: int | None = Query(default=None, ge=2000, description="Year filter (>= 2000)"),
    type: str = Query(default="expense", description="Classification type: 'expense' or 'income'"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve category-wise spending distribution."""
    family, _ = family_ctx
    return await ReportService.get_category_report(
        session=db,
        family=family,
        from_date=from_date,
        to_date=to_date,
        month=month,
        year=year,
        category_type=type,
    )


@router.get(
    "/members",
    response_model=MemberReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Member Contribution Report",
    description="Retrieve member-wise breakdown ('Husband vs Wife') showing who paid how much, personal vs shared expenses, and income contributions.",
)
async def get_member_report(
    from_date: date | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    to_date: date | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    month: int | None = Query(default=None, ge=1, le=12, description="Month filter (1-12)"),
    year: int | None = Query(default=None, ge=2000, description="Year filter (>= 2000)"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve member-wise spending & earnings report."""
    family, _ = family_ctx
    return await ReportService.get_member_report(
        session=db,
        family=family,
        from_date=from_date,
        to_date=to_date,
        month=month,
        year=year,
    )


@router.get(
    "/payment-methods",
    response_model=PaymentMethodReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Payment Methods Report",
    description="Retrieve spending breakdown across payment instruments (credit card, cash, UPI, debit card, bank transfer).",
)
async def get_payment_method_report(
    from_date: date | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    to_date: date | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    month: int | None = Query(default=None, ge=1, le=12, description="Month filter (1-12)"),
    year: int | None = Query(default=None, ge=2000, description="Year filter (>= 2000)"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve payment method breakdown report."""
    family, _ = family_ctx
    return await ReportService.get_payment_method_report(
        session=db,
        family=family,
        from_date=from_date,
        to_date=to_date,
        month=month,
        year=year,
    )
