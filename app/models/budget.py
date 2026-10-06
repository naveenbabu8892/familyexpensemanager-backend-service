import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.family import Family
    from app.models.category import Category


class Budget(Base, TimestampMixin):
    """Budget allocated for a specific category or family as a whole for a given month and year."""

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )  # NULL represents total overall family monthly budget
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Table constraints and multi-column indexes
    __table_args__ = (
        CheckConstraint("amount > 0", name="check_budget_amount_positive"),
        CheckConstraint("month >= 1 AND month <= 12", name="check_budget_month_range"),
        CheckConstraint("year >= 2000", name="check_budget_year_valid"),
        UniqueConstraint("family_id", "category_id", "month", "year", name="uq_budget_family_category_month_year"),
        Index("ix_budgets_family_year_month", "family_id", "year", "month"),
    )

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="budgets")
    category: Mapped["Category | None"] = relationship("Category", back_populates="budgets")
    creator: Mapped["User | None"] = relationship(
        "User",
        back_populates="budgets_created",
        foreign_keys=[created_by],
    )

    def __repr__(self) -> str:
        return f"<Budget id={self.id} family_id={self.family_id} category_id={self.category_id} {self.month}/{self.year} amount={self.amount}>"
