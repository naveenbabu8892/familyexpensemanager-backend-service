from datetime import date
from decimal import Decimal
import math
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Income
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.repositories.family_repository import FamilyRepository
from app.repositories.income_repository import IncomeRepository
from app.schemas.income import (
    IncomeCreateRequest,
    IncomeListResponse,
    IncomeResponse,
    IncomeUpdateRequest,
)


class IncomeService:
    """Service handling income creation, retrieval, filtering, updates, and deletion."""

    @staticmethod
    async def create_income(
        session: AsyncSession, user: User, data: IncomeCreateRequest
    ) -> IncomeResponse:
        """
        Record a new income entry for the authenticated user's family.
        Validates:
        - User belongs to an active family.
        - Category belongs to user's family or is a default (if provided).
        - Recipient (received_by) belongs to user's family.
        """
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family. Join or create a family first.",
            )
        family, _ = family_ctx

        # Validate category accessibility if provided
        cat_id = None
        if data.category_id:
            category = await CategoryRepository.get_accessible_category(
                session, data.category_id, family.id
            )
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The specified category does not exist or does not belong to your family.",
                )
            cat_id = category.id

        # Validate received_by member
        recipient_id = data.received_by if data.received_by is not None else user.id
        recipient_membership = await FamilyRepository.get_user_membership(session, recipient_id)
        if not recipient_membership or recipient_membership.family_id != family.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The user specified in 'received_by' is not a member of your family.",
            )

        currency = (data.currency or family.currency).upper().strip()

        income = Income(
            family_id=family.id,
            user_id=recipient_id,
            category_id=cat_id,
            amount=data.amount,
            currency=currency,
            income_date=data.income_date,
            title=data.title.strip(),
            description=data.description.strip() if data.description else None,
        )
        created_income = await IncomeRepository.create(session, income)

        res = await IncomeRepository.get_by_id_and_family(
            session, created_income.id, family.id
        )
        assert res is not None
        inc, cat_name, received_by_name = res

        return IncomeResponse(
            id=inc.id,
            family_id=inc.family_id,
            received_by=inc.user_id,
            category_id=inc.category_id,
            amount=inc.amount,
            currency=inc.currency,
            income_date=inc.income_date,
            title=inc.title,
            description=inc.description,
            created_at=inc.created_at,
            updated_at=inc.updated_at,
            category_name=cat_name,
            received_by_name=received_by_name,
        )

    @staticmethod
    async def get_income(
        session: AsyncSession, user: User, income_id: uuid.UUID
    ) -> IncomeResponse:
        """Fetch a single income by ID within the user's family."""
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        res = await IncomeRepository.get_by_id_and_family(session, income_id, family.id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Income record not found.",
            )

        inc, cat_name, received_by_name = res
        return IncomeResponse(
            id=inc.id,
            family_id=inc.family_id,
            received_by=inc.user_id,
            category_id=inc.category_id,
            amount=inc.amount,
            currency=inc.currency,
            income_date=inc.income_date,
            title=inc.title,
            description=inc.description,
            created_at=inc.created_at,
            updated_at=inc.updated_at,
            category_name=cat_name,
            received_by_name=received_by_name,
        )

    @staticmethod
    async def update_income(
        session: AsyncSession,
        user: User,
        income_id: uuid.UUID,
        data: IncomeUpdateRequest,
    ) -> IncomeResponse:
        """Update an existing income record within the user's family."""
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        res = await IncomeRepository.get_by_id_and_family(session, income_id, family.id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Income record not found.",
            )
        inc, _, _ = res

        if data.category_id is not None:
            category = await CategoryRepository.get_accessible_category(
                session, data.category_id, family.id
            )
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The specified category does not exist or does not belong to your family.",
                )
            inc.category_id = category.id

        if data.received_by is not None:
            recipient_membership = await FamilyRepository.get_user_membership(session, data.received_by)
            if not recipient_membership or recipient_membership.family_id != family.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The user specified in 'received_by' is not a member of your family.",
                )
            inc.user_id = data.received_by

        if data.amount is not None:
            inc.amount = data.amount
        if data.currency is not None:
            inc.currency = data.currency.upper().strip()
        if data.income_date is not None:
            inc.income_date = data.income_date
        if data.title is not None:
            inc.title = data.title.strip()
        if data.description is not None:
            inc.description = data.description.strip() if data.description else None

        await IncomeRepository.update(session, inc)

        updated_res = await IncomeRepository.get_by_id_and_family(session, inc.id, family.id)
        assert updated_res is not None
        u_inc, u_cat, u_rec = updated_res

        return IncomeResponse(
            id=u_inc.id,
            family_id=u_inc.family_id,
            received_by=u_inc.user_id,
            category_id=u_inc.category_id,
            amount=u_inc.amount,
            currency=u_inc.currency,
            income_date=u_inc.income_date,
            title=u_inc.title,
            description=u_inc.description,
            created_at=u_inc.created_at,
            updated_at=u_inc.updated_at,
            category_name=u_cat,
            received_by_name=u_rec,
        )

    @staticmethod
    async def delete_income(
        session: AsyncSession, user: User, income_id: uuid.UUID
    ) -> None:
        """Delete an income record."""
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        res = await IncomeRepository.get_by_id_and_family(session, income_id, family.id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Income record not found.",
            )
        inc, _, _ = res
        await IncomeRepository.delete(session, inc)

    @staticmethod
    async def list_income(
        session: AsyncSession,
        user: User,
        page: int = 1,
        page_size: int = 20,
        from_date: date | None = None,
        to_date: date | None = None,
        category_id: uuid.UUID | None = None,
        received_by: uuid.UUID | None = None,
        sort_by: str = "income_date",
        sort_order: str = "desc",
    ) -> IncomeListResponse:
        """
        List income records for the user's family with pagination, date, category, and person filtering.
        """
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        offset = (page - 1) * page_size
        items_data, total_count, total_amount = await IncomeRepository.list_income(
            session=session,
            family_id=family.id,
            from_date=from_date,
            to_date=to_date,
            category_id=category_id,
            received_by=received_by,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=page_size,
        )

        income_items = [
            IncomeResponse(
                id=inc.id,
                family_id=inc.family_id,
                received_by=inc.user_id,
                category_id=inc.category_id,
                amount=inc.amount,
                currency=inc.currency,
                income_date=inc.income_date,
                title=inc.title,
                description=inc.description,
                created_at=inc.created_at,
                updated_at=inc.updated_at,
                category_name=cat_name,
                received_by_name=rec_name,
            )
            for inc, cat_name, rec_name in items_data
        ]

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return IncomeListResponse(
            items=income_items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_amount=total_amount,
        )
