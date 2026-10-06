import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.family import Family
    from app.models.category import Category


class Expense(Base, TimestampMixin):
    """Expense transaction recorded within a family."""

    __tablename__ = "expenses"

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
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    paid_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD", nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(
        String(30),
        default="cash",
        server_default="cash",
        nullable=False,
    )  # 'cash', 'credit_card', 'debit_card', 'upi', 'bank_transfer', etc.
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # Table constraints and multi-column indexes
    __table_args__ = (
        CheckConstraint("amount > 0", name="check_expense_amount_positive"),
        Index("ix_expenses_family_date", "family_id", "expense_date"),
        Index("ix_expenses_family_category", "family_id", "category_id"),
    )

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="expenses")
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="expenses_created",
        foreign_keys=[created_by],
    )
    payer: Mapped["User"] = relationship(
        "User",
        back_populates="expenses_paid",
        foreign_keys=[paid_by],
    )
    category: Mapped["Category"] = relationship("Category", back_populates="expenses")

    def __repr__(self) -> str:
        return f"<Expense id={self.id} amount={self.amount} {self.currency} title='{self.title}'>"


class Income(Base, TimestampMixin):
    """Income entry earned by a family member."""

    __tablename__ = "incomes"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD", nullable=False)
    income_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Table constraints and multi-column indexes
    __table_args__ = (
        CheckConstraint("amount > 0", name="check_income_amount_positive"),
        Index("ix_incomes_family_date", "family_id", "income_date"),
        Index("ix_incomes_family_user", "family_id", "user_id"),
    )

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="incomes")
    user: Mapped["User"] = relationship("User", back_populates="incomes", foreign_keys=[user_id])
    category: Mapped["Category | None"] = relationship("Category", back_populates="incomes")

    def __repr__(self) -> str:
        return f"<Income id={self.id} amount={self.amount} {self.currency} title='{self.title}'>"
