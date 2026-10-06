import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.family import Family
    from app.models.transaction import Expense, Income
    from app.models.budget import Budget


class Category(Base):
    """Expense and Income classification categories."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    family_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )  # NULL indicates system-wide default category
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Material icon identifier
    color: Mapped[str | None] = mapped_column(String(10), nullable=True)  # Hex color code (e.g., #FF5722)
    type: Mapped[str] = mapped_column(
        String(20),
        default="expense",
        server_default="expense",
        nullable=False,
    )  # 'expense', 'income', 'both'
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('expense', 'income', 'both')",
            name="check_category_type",
        ),
        UniqueConstraint("family_id", "name", "type", name="uq_categories_family_name_type"),
        Index("ix_categories_family_type", "family_id", "type"),
        Index(
            "uq_categories_default_name_type",
            "name",
            "type",
            unique=True,
            postgresql_where=text("family_id IS NULL"),
        ),
    )

    # Relationships
    family: Mapped["Family | None"] = relationship("Family", back_populates="categories")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="category")
    incomes: Mapped[list["Income"]] = relationship("Income", back_populates="category")
    budgets: Mapped[list["Budget"]] = relationship("Budget", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name} type={self.type}>"
