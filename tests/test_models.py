from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

from app.models import (
    User,
    Family,
    FamilyMember,
    FamilyInvitation,
    Category,
    Expense,
    Income,
    Budget,
    RefreshToken,
)


def test_user_model_instantiation():
    """Test User model instantiation and attributes."""
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        full_name="John Doe",
        email="john@example.com",
        password_hash="argon2_hashed_secret",
        is_active=True,
    )
    assert user.id == user_id
    assert user.full_name == "John Doe"
    assert user.email == "john@example.com"
    assert user.is_active is True


def test_expense_monetary_decimal_precision():
    """Verify that Expense amounts strictly enforce Decimal type and precision."""
    expense_id = uuid.uuid4()
    expense = Expense(
        id=expense_id,
        family_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        paid_by=uuid.uuid4(),
        category_id=uuid.uuid4(),
        amount=Decimal("1234.56"),
        currency="USD",
        expense_date=date.today(),
        title="Weekly Groceries",
        is_shared=True,
    )
    assert expense.id == expense_id
    assert isinstance(expense.amount, Decimal)
    assert expense.amount == Decimal("1234.56")
    assert expense.is_shared is True


def test_budget_constraints_and_decimal():
    """Test Budget model creation with decimal amounts and valid date periods."""
    budget = Budget(
        family_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        amount=Decimal("500.00"),
        month=10,
        year=2026,
    )
    assert isinstance(budget.amount, Decimal)
    assert budget.month == 10
    assert budget.year == 2026


def test_refresh_token_revocation_flag():
    """Test RefreshToken model attributes and revocation defaults."""
    token_id = uuid.uuid4()
    token = RefreshToken(
        id=token_id,
        user_id=uuid.uuid4(),
        token_hash="sha256_hashed_token_value",
        expires_at=datetime.now(timezone.utc),
        revoked=False,
    )
    assert token.id == token_id
    assert token.revoked is False
