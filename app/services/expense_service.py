from datetime import date
from decimal import Decimal
import math
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Expense
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.family_repository import FamilyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.expense import (
    ExpenseCreateRequest,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseUpdateRequest,
)


class ExpenseService:
    """Service handling expense creation, retrieval, filtering, updates, and deletion."""

    @staticmethod
    async def create_expense(
        session: AsyncSession, user: User, data: ExpenseCreateRequest
    ) -> ExpenseResponse:
        """
        Record a new expense.
        Validates:
        - User belongs to an active family.
        - Category belongs to user's family or is a default.
        - Payer (paid_by) belongs to user's family.
        """
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family. Join or create a family first.",
            )
        family, _ = family_ctx

        # Validate category accessibility
        category = await CategoryRepository.get_accessible_category(
            session, data.category_id, family.id
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The specified category does not exist or does not belong to your family.",
            )

        # Validate paid_by member
        payer_id = data.paid_by if data.paid_by is not None else user.id
        payer_membership = await FamilyRepository.get_user_membership(session, payer_id)
        if not payer_membership or payer_membership.family_id != family.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The user specified in 'paid_by' is not a member of your family.",
            )

        currency = (data.currency or family.currency).upper().strip()

        expense = Expense(
            family_id=family.id,
            created_by=user.id,
            paid_by=payer_id,
            category_id=category.id,
            amount=data.amount,
            currency=currency,
            expense_date=data.expense_date,
            payment_method=data.payment_method.lower().strip(),
            title=data.title.strip(),
            description=data.description.strip() if data.description else None,
            is_shared=data.is_shared,
        )
        created_expense = await ExpenseRepository.create(session, expense)

        # Fetch with joined names for response
        res = await ExpenseRepository.get_by_id_and_family(
            session, created_expense.id, family.id
        )
        assert res is not None
        exp, cat_name, paid_by_name, created_by_name = res

        return ExpenseResponse(
            id=exp.id,
            family_id=exp.family_id,
            created_by=exp.created_by,
            paid_by=exp.paid_by,
            category_id=exp.category_id,
            amount=exp.amount,
            currency=exp.currency,
            expense_date=exp.expense_date,
            payment_method=exp.payment_method,
            title=exp.title,
            description=exp.description,
            is_shared=exp.is_shared,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            category_name=cat_name,
            paid_by_name=paid_by_name,
            created_by_name=created_by_name,
        )

    @staticmethod
    async def get_expense(
        session: AsyncSession, user: User, expense_id: uuid.UUID
    ) -> ExpenseResponse:
        """Fetch a single expense by ID within the user's family."""
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        res = await ExpenseRepository.get_by_id_and_family(session, expense_id, family.id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found.",
            )

        exp, cat_name, paid_by_name, created_by_name = res
        return ExpenseResponse(
            id=exp.id,
            family_id=exp.family_id,
            created_by=exp.created_by,
            paid_by=exp.paid_by,
            category_id=exp.category_id,
            amount=exp.amount,
            currency=exp.currency,
            expense_date=exp.expense_date,
            payment_method=exp.payment_method,
            title=exp.title,
            description=exp.description,
            is_shared=exp.is_shared,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            category_name=cat_name,
            paid_by_name=paid_by_name,
            created_by_name=created_by_name,
        )

    @staticmethod
    async def update_expense(
        session: AsyncSession,
        user: User,
        expense_id: uuid.UUID,
        data: ExpenseUpdateRequest,
    ) -> ExpenseResponse:
        """Update an existing expense within the user's family."""
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        res = await ExpenseRepository.get_by_id_and_family(session, expense_id, family.id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found.",
            )
        exp, _, _, _ = res

        if data.category_id is not None:
            category = await CategoryRepository.get_accessible_category(
                session, data.category_id, family.id
            )
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The specified category does not exist or does not belong to your family.",
                )
            exp.category_id = category.id

        if data.paid_by is not None:
            payer_membership = await FamilyRepository.get_user_membership(session, data.paid_by)
            if not payer_membership or payer_membership.family_id != family.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The user specified in 'paid_by' is not a member of your family.",
                )
            exp.paid_by = data.paid_by

        if data.amount is not None:
            exp.amount = data.amount
        if data.currency is not None:
            exp.currency = data.currency.upper().strip()
        if data.expense_date is not None:
            exp.expense_date = data.expense_date
        if data.payment_method is not None:
            exp.payment_method = data.payment_method.lower().strip()
        if data.title is not None:
            exp.title = data.title.strip()
        if data.description is not None:
            exp.description = data.description.strip() if data.description else None
        if data.is_shared is not None:
            exp.is_shared = data.is_shared

        await ExpenseRepository.update(session, exp)

        updated_res = await ExpenseRepository.get_by_id_and_family(session, exp.id, family.id)
        assert updated_res is not None
        u_exp, u_cat, u_paid_by, u_created_by = updated_res

        return ExpenseResponse(
            id=u_exp.id,
            family_id=u_exp.family_id,
            created_by=u_exp.created_by,
            paid_by=u_exp.paid_by,
            category_id=u_exp.category_id,
            amount=u_exp.amount,
            currency=u_exp.currency,
            expense_date=u_exp.expense_date,
            payment_method=u_exp.payment_method,
            title=u_exp.title,
            description=u_exp.description,
            is_shared=u_exp.is_shared,
            created_at=u_exp.created_at,
            updated_at=u_exp.updated_at,
            category_name=u_cat,
            paid_by_name=u_paid_by,
            created_by_name=u_created_by,
        )

    @staticmethod
    async def delete_expense(
        session: AsyncSession, user: User, expense_id: uuid.UUID
    ) -> None:
        """Delete an expense record."""
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        res = await ExpenseRepository.get_by_id_and_family(session, expense_id, family.id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found.",
            )
        exp, _, _, _ = res
        await ExpenseRepository.delete(session, exp)

    @staticmethod
    async def list_expenses(
        session: AsyncSession,
        user: User,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        category_id: uuid.UUID | None = None,
        paid_by: uuid.UUID | None = None,
        payment_method: str | None = None,
        is_shared: bool | None = None,
        sort_by: str = "expense_date",
        sort_order: str = "desc",
    ) -> ExpenseListResponse:
        """
        List expenses for the user's family with pagination, searching, filtering, and sorting.
        """
        family_ctx = await FamilyRepository.get_user_family_and_membership(session, user.id)
        if not family_ctx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You do not belong to any family.",
            )
        family, _ = family_ctx

        offset = (page - 1) * page_size
        items_data, total_count, total_amount = await ExpenseRepository.list_expenses(
            session=session,
            family_id=family.id,
            search=search,
            from_date=from_date,
            to_date=to_date,
            category_id=category_id,
            paid_by=paid_by,
            payment_method=payment_method,
            is_shared=is_shared,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=page_size,
        )

        expense_items = [
            ExpenseResponse(
                id=exp.id,
                family_id=exp.family_id,
                created_by=exp.created_by,
                paid_by=exp.paid_by,
                category_id=exp.category_id,
                amount=exp.amount,
                currency=exp.currency,
                expense_date=exp.expense_date,
                payment_method=exp.payment_method,
                title=exp.title,
                description=exp.description,
                is_shared=exp.is_shared,
                created_at=exp.created_at,
                updated_at=exp.updated_at,
                category_name=cat_name,
                paid_by_name=paid_name,
                created_by_name=creator_name,
            )
            for exp, cat_name, paid_name, creator_name in items_data
        ]

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return ExpenseListResponse(
            items=expense_items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_amount=total_amount,
        )
