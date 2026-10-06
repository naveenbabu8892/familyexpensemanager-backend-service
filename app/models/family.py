import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.category import Category
    from app.models.transaction import Expense, Income
    from app.models.budget import Budget


class Family(Base, TimestampMixin):
    """Family unit entity grouping multiple users and their financial records."""

    __tablename__ = "families"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", server_default="UTC", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    creator: Mapped["User"] = sa_relationship(
        "User",
        back_populates="created_families",
        foreign_keys=[created_by],
    )
    members: Mapped[list["FamilyMember"]] = sa_relationship(
        "FamilyMember",
        back_populates="family",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list["FamilyInvitation"]] = sa_relationship(
        "FamilyInvitation",
        back_populates="family",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["Category"]] = sa_relationship(
        "Category",
        back_populates="family",
        cascade="all, delete-orphan",
    )
    expenses: Mapped[list["Expense"]] = sa_relationship(
        "Expense",
        back_populates="family",
        cascade="all, delete-orphan",
    )
    incomes: Mapped[list["Income"]] = sa_relationship(
        "Income",
        back_populates="family",
        cascade="all, delete-orphan",
    )
    budgets: Mapped[list["Budget"]] = sa_relationship(
        "Budget",
        back_populates="family",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Family id={self.id} name={self.name}>"


class FamilyMember(Base):
    """Association between User and Family with member roles and statuses."""

    __tablename__ = "family_members"

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
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        default="member",
        server_default="member",
        nullable=False,
    )  # e.g., 'owner', 'admin', 'member'
    relationship: Mapped[str] = mapped_column(
        String(50),
        default="other",
        server_default="other",
        nullable=False,
    )  # e.g., 'husband', 'wife', 'father', 'mother', 'other'
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        server_default="active",
        nullable=False,
    )  # e.g., 'active', 'pending', 'inactive'
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("family_id", "user_id", name="uq_family_members_family_user"),
        Index("ix_family_members_family_user", "family_id", "user_id"),
    )

    # Relationships
    family: Mapped["Family"] = sa_relationship("Family", back_populates="members")
    user: Mapped["User"] = sa_relationship("User", back_populates="family_memberships")

    def __repr__(self) -> str:
        return f"<FamilyMember family_id={self.family_id} user_id={self.user_id} role={self.role} relationship={self.relationship}>"


class FamilyInvitation(Base):
    """Pending/accepted invitations to join a family."""

    __tablename__ = "family_invitations"

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
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relationship: Mapped[str] = mapped_column(
        String(50),
        default="other",
        server_default="other",
        nullable=False,
    )  # intended family relationship
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )  # 'pending', 'accepted', 'expired', 'revoked'
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    family: Mapped["Family"] = sa_relationship("Family", back_populates="invitations")
    inviter: Mapped["User"] = sa_relationship(
        "User",
        back_populates="sent_invitations",
        foreign_keys=[invited_by],
    )

    def __repr__(self) -> str:
        return f"<FamilyInvitation token={self.token} email={self.invited_email} status={self.status}>"
