import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryDeleteResponse,
    CategoryResponse,
    CategoryUpdateRequest,
)


class CategoryService:
    """Business logic for category management."""

    @staticmethod
    async def list_categories(
        session: AsyncSession, family_id: uuid.UUID, category_type: str | None = None
    ) -> list[CategoryResponse]:
        """
        List all categories accessible to the family.
        Includes system defaults (family_id IS NULL) and family custom categories.
        """
        normalized_type = category_type.lower().strip() if category_type else None
        if normalized_type and normalized_type not in ("expense", "income", "both"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid category type filter. Allowed values: 'expense', 'income', 'both'.",
            )

        categories = await CategoryRepository.list_for_family(session, family_id, normalized_type)
        return [CategoryResponse.model_validate(cat) for cat in categories]

    @staticmethod
    async def create_category(
        session: AsyncSession, family_id: uuid.UUID, data: CategoryCreateRequest
    ) -> CategoryResponse:
        """
        Create a custom category for the user's family.
        Rules:
        - Category name must be unique within the family/default pool for that type.
        - Cannot create default categories via this endpoint (always is_default=False).
        """
        name = data.name.strip()
        cat_type = data.type.lower().strip()

        # Check for duplicate category name
        conflict = await CategoryRepository.is_name_conflict(session, family_id, name, cat_type)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A category named '{name}' with type '{cat_type}' already exists.",
            )

        category = Category(
            id=uuid.uuid4(),
            family_id=family_id,
            name=name,
            icon=data.icon.strip() if data.icon else None,
            color=data.color.strip() if data.color else None,
            type=cat_type,
            is_default=False,
        )
        created = await CategoryRepository.create(session, category)
        return CategoryResponse.model_validate(created)

    @staticmethod
    async def update_category(
        session: AsyncSession,
        family_id: uuid.UUID,
        category_id: uuid.UUID,
        data: CategoryUpdateRequest,
    ) -> CategoryResponse:
        """
        Update an existing custom family category.
        Rules:
        - System default categories cannot be modified (HTTP 403).
        - Categories belonging to other families cannot be accessed/modified (HTTP 404).
        - If name or type changes, uniqueness constraint is re-checked.
        """
        category = await CategoryRepository.get_by_id(session, category_id)
        if not category or (category.family_id is not None and category.family_id != family_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )

        if category.is_default or category.family_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System default categories cannot be modified.",
            )

        new_name = data.name.strip() if data.name is not None else category.name
        new_type = data.type.lower().strip() if data.type is not None else category.type

        # Check duplicate if name or type changed
        if new_name.lower() != category.name.lower() or new_type != category.type:
            conflict = await CategoryRepository.is_name_conflict(
                session, family_id, new_name, new_type, exclude_id=category.id
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A category named '{new_name}' with type '{new_type}' already exists.",
                )

        if data.name is not None:
            category.name = new_name
        if data.type is not None:
            category.type = new_type
        if data.icon is not None:
            category.icon = data.icon.strip() if data.icon else None
        if data.color is not None:
            category.color = data.color.strip() if data.color else None

        updated = await CategoryRepository.update(session, category)
        return CategoryResponse.model_validate(updated)

    @staticmethod
    async def delete_category(
        session: AsyncSession, family_id: uuid.UUID, category_id: uuid.UUID
    ) -> CategoryDeleteResponse:
        """
        Delete a custom family category.
        Rules:
        - System default categories cannot be deleted (HTTP 403).
        - Categories belonging to other families cannot be deleted (HTTP 404).
        - Cannot delete a category that has active expenses, incomes, or budgets (HTTP 400).
        """
        category = await CategoryRepository.get_by_id(session, category_id)
        if not category or (category.family_id is not None and category.family_id != family_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )

        if category.is_default or category.family_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System default categories cannot be deleted.",
            )

        # Integrity check: Ensure category is not referenced in transactions or budgets
        refs = await CategoryRepository.count_references(session, category.id)
        if refs["total"] > 0:
            reasons = []
            if refs["expenses"] > 0:
                reasons.append(f"{refs['expenses']} expense(s)")
            if refs["incomes"] > 0:
                reasons.append(f"{refs['incomes']} income(s)")
            if refs["budgets"] > 0:
                reasons.append(f"{refs['budgets']} budget(s)")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete category: it is associated with {', '.join(reasons)}.",
            )

        await CategoryRepository.delete(session, category)
        return CategoryDeleteResponse(
            message="Category deleted successfully.",
            category_id=category_id,
        )
