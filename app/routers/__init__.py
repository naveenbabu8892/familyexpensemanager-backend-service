"""API routers package."""

from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.families import router as families_router
from app.routers.categories import router as categories_router
from app.routers.expenses import router as expenses_router
from app.routers.income import router as income_router
from app.routers.budgets import router as budgets_router
from app.routers.dashboard import router as dashboard_router
from app.routers.reports import router as reports_router
from app.routers.relationships import router as relationships_router

__all__ = [
    "health_router",
    "auth_router",
    "users_router",
    "families_router",
    "categories_router",
    "expenses_router",
    "income_router",
    "budgets_router",
    "dashboard_router",
    "reports_router",
    "relationships_router",
]
