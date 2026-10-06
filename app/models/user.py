import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.family import Family, FamilyMember, FamilyInvitation
    from app.models.transaction import Expense, Income
    from app.models.budget import Budget
    from app.models.token import RefreshToken


class User(Base, TimestampMixin):
    """User account entity."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # Relationships
    created_families: Mapped[list["Family"]] = relationship(
        "Family",
        back_populates="creator",
        foreign_keys="Family.created_by",
    )
    family_memberships: Mapped[list["FamilyMember"]] = relationship(
        "FamilyMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sent_invitations: Mapped[list["FamilyInvitation"]] = relationship(
        "FamilyInvitation",
        back_populates="inviter",
        foreign_keys="FamilyInvitation.invited_by",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    expenses_created: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="creator",
        foreign_keys="Expense.created_by",
    )
    expenses_paid: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="payer",
        foreign_keys="Expense.paid_by",
    )
    incomes: Mapped[list["Income"]] = relationship(
        "Income",
        back_populates="user",
    )
    budgets_created: Mapped[list["Budget"]] = relationship(
        "Budget",
        back_populates="creator",
        foreign_keys="Budget.created_by",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
