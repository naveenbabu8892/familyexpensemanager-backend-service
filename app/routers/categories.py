import uuid
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.family import get_current_family_context
from app.models.family import Family, FamilyMember
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryDeleteResponse,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get(
    "",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Family Categories",
    description="List all categories accessible to the family (system defaults + custom categories), optionally filtered by type.",
)
async def list_categories(
    type: str | None = Query(
        default=None,
        description="Filter by category type: 'expense', 'income', or 'both' (case-insensitive)",
    ),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all categories available to the authenticated family."""
    family, _ = family_ctx
    return await CategoryService.list_categories(db, family.id, category_type=type)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Category",
    description="Create a new custom category for the authenticated user's family.",
)
async def create_category(
    data: CategoryCreateRequest,
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Create a new custom category."""
    family, _ = family_ctx
    return await CategoryService.create_category(db, family.id, data)


@router.put(
    "/{id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Custom Category",
    description="Update an existing custom category belonging to the authenticated user's family.",
)
async def update_category(
    id: uuid.UUID = Path(..., description="Unique ID of the category to update"),
    data: CategoryUpdateRequest = ...,
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Update a custom category."""
    family, _ = family_ctx
    return await CategoryService.update_category(db, family.id, id, data)


@router.delete(
    "/{id}",
    response_model=CategoryDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Custom Category",
    description="Delete a custom category. Default categories and categories in active use cannot be deleted.",
)
async def delete_category(
    id: uuid.UUID = Path(..., description="Unique ID of the category to delete"),
    family_ctx: tuple[Family, FamilyMember] = Depends(get_current_family_context),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom category."""
    family, _ = family_ctx
    return await CategoryService.delete_category(db, family.id, id)
