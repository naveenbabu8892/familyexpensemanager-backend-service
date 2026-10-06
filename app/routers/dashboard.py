from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.family import get_current_family_context
from app.models.family import Family, FamilyMember
from app.models.user import User
from app.schemas.report import DashboardResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Financial Dashboard",
    description="Retrieve consolidated family financial overview with income, expenses, personal vs shared breakdown, spouse comparison, active budget health, and recent transactions.",
)
async def get_dashboard(
    from_date: date | None = Query(default=None, description="Start date filter (YYYY-MM-DD)"),
    to_date: date | None = Query(default=None, description="End date filter (YYYY-MM-DD)"),
    month: int | None = Query(default=None, ge=1, le=12, description="Month filter (1-12)"),
    year: int | None = Query(default=None, ge=2000, description="Year filter (>= 2000)"),
    current_user: User = Depends(get_current_active_user),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve family financial dashboard."""
    family, _ = family_ctx
    return await ReportService.get_dashboard(
        session=db,
        family=family,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date,
        month=month,
        year=year,
    )
