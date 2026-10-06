import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Expense, Income

DEFAULT_EXPENSE_CATEGORIES = [
    {"name": "Grocery", "icon": "shopping_cart", "color": "#4CAF50", "type": "expense"},
    {"name": "Rent", "icon": "home", "color": "#2196F3", "type": "expense"},
    {"name": "Electricity", "icon": "bolt", "color": "#FFC107", "type": "expense"},
    {"name": "Internet", "icon": "wifi", "color": "#00BCD4", "type": "expense"},
    {"name": "Fuel", "icon": "local_gas_station", "color": "#FF5722", "type": "expense"},
    {"name": "Shopping", "icon": "shopping_bag", "color": "#E91E63", "type": "expense"},
    {"name": "Dining", "icon": "restaurant", "color": "#FF9800", "type": "expense"},
    {"name": "Medical", "icon": "medical_services", "color": "#F44336", "type": "expense"},
    {"name": "Education", "icon": "school", "color": "#3F51B5", "type": "expense"},
    {"name": "Travel", "icon": "flight", "color": "#009688", "type": "expense"},
    {"name": "Entertainment", "icon": "movie", "color": "#9C27B0", "type": "expense"},
    {"name": "Insurance", "icon": "security", "color": "#607D8B", "type": "expense"},
    {"name": "EMI", "icon": "account_balance", "color": "#795548", "type": "expense"},
    {"name": "Household", "icon": "cottage", "color": "#8BC34A", "type": "expense"},
    {"name": "Other", "icon": "more_horiz", "color": "#9E9E9E", "type": "expense"},
]

DEFAULT_INCOME_CATEGORIES = [
    {"name": "Salary", "icon": "payments", "color": "#4CAF50", "type": "income"},
    {"name": "Freelance", "icon": "laptop_mac", "color": "#2196F3", "type": "income"},
    {"name": "Business", "icon": "store", "color": "#9C27B0", "type": "income"},
    {"name": "Bonus", "icon": "military_tech", "color": "#FFC107", "type": "income"},
    {"name": "Interest", "icon": "savings", "color": "#00BCD4", "type": "income"},
    {"name": "Investment", "icon": "trending_up", "color": "#009688", "type": "income"},
    {"name": "Gift", "icon": "card_giftcard", "color": "#E91E63", "type": "income"},
    {"name": "Other", "icon": "attach_money", "color": "#9E9E9E", "type": "income"},
]

ALL_SYSTEM_CATEGORIES = DEFAULT_EXPENSE_CATEGORIES + DEFAULT_INCOME_CATEGORIES


class CategoryRepository:
    """Data access repository for Categories."""

    @staticmethod
    async def get_by_id(session: AsyncSession, category_id: uuid.UUID) -> Category | None:
        """Fetch category by ID."""
        result = await session.execute(select(Category).where(Category.id == category_id))
        return result.scalars().first()

    @staticmethod
    async def get_accessible_category(
        session: AsyncSession, category_id: uuid.UUID, family_id: uuid.UUID
    ) -> Category | None:
        """
        Verify that a category is accessible to a family.
        A category is accessible if it belongs to the family OR is a system-wide default (family_id is None).
        """
        stmt = select(Category).where(
            Category.id == category_id,
            or_(Category.family_id == family_id, Category.family_id.is_(None)),
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def list_for_family(
        session: AsyncSession, family_id: uuid.UUID, category_type: str | None = None
    ) -> list[Category]:
        """Fetch all categories accessible to a family (system defaults + custom categories)."""
        conditions = [or_(Category.family_id == family_id, Category.family_id.is_(None))]
        if category_type:
            conditions.append(or_(Category.type == category_type, Category.type == "both"))

        stmt = (
            select(Category)
            .where(*conditions)
            .order_by(Category.is_default.desc(), Category.name.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def is_name_conflict(
        session: AsyncSession,
        family_id: uuid.UUID,
        name: str,
        category_type: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check if a category with the same name and matching type exists
        in either the user's family or as a system default.
        """
        type_conditions = or_(
            Category.type == category_type,
            Category.type == "both",
            category_type == "both",
        )
        family_conditions = or_(Category.family_id == family_id, Category.family_id.is_(None))
        stmt = select(Category.id).where(
            func.lower(Category.name) == name.lower().strip(),
            family_conditions,
            type_conditions,
        )
        if exclude_id is not None:
            stmt = stmt.where(Category.id != exclude_id)

        result = await session.execute(stmt)
        return result.scalars().first() is not None

    @staticmethod
    async def create(session: AsyncSession, category: Category) -> Category:
        """Persist a new Category."""
        session.add(category)
        await session.flush()
        await session.refresh(category)
        return category

    @staticmethod
    async def update(session: AsyncSession, category: Category) -> Category:
        """Update an existing Category."""
        await session.flush()
        await session.refresh(category)
        return category

    @staticmethod
    async def delete(session: AsyncSession, category: Category) -> None:
        """Delete a Category."""
        await session.delete(category)
        await session.flush()

    @staticmethod
    async def count_references(session: AsyncSession, category_id: uuid.UUID) -> dict[str, int]:
        """Count active references to this category across expenses, incomes, and budgets."""
        exp_stmt = select(func.count(Expense.id)).where(Expense.category_id == category_id)
        inc_stmt = select(func.count(Income.id)).where(Income.category_id == category_id)
        bud_stmt = select(func.count(Budget.id)).where(Budget.category_id == category_id)

        exp_count = (await session.execute(exp_stmt)).scalar_one()
        inc_count = (await session.execute(inc_stmt)).scalar_one()
        bud_count = (await session.execute(bud_stmt)).scalar_one()

        return {
            "expenses": exp_count,
            "incomes": inc_count,
            "budgets": bud_count,
            "total": exp_count + inc_count + bud_count,
        }

    @staticmethod
    async def seed_system_default_categories(session: AsyncSession) -> tuple[int, int]:
        """
        Safely and idempotently seed system-wide default categories (family_id=None, is_default=True).
        Returns (created_count, existing_count).
        """
        created_count = 0
        existing_count = 0

        for cat_def in ALL_SYSTEM_CATEGORIES:
            stmt = select(Category).where(
                Category.family_id.is_(None),
                func.lower(Category.name) == cat_def["name"].lower(),
                Category.type == cat_def["type"],
            )
            result = await session.execute(stmt)
            existing = result.scalars().first()

            if existing:
                # Update attributes if needed
                existing.icon = cat_def["icon"]
                existing.color = cat_def["color"]
                existing.is_default = True
                existing_count += 1
            else:
                new_cat = Category(
                    id=uuid.uuid4(),
                    family_id=None,
                    name=cat_def["name"],
                    icon=cat_def["icon"],
                    color=cat_def["color"],
                    type=cat_def["type"],
                    is_default=True,
                )
                session.add(new_cat)
                created_count += 1

        await session.flush()
        return created_count, existing_count
