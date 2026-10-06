from datetime import date
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient


async def create_user_and_family(
    client: AsyncClient, name: str, email: str, fam_name: str
) -> tuple[str, str]:
    """Helper to register user, create family, and return (token, family_id)."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "Password123!"},
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fam_resp = await client.post(
        "/api/v1/families",
        json={"name": fam_name, "currency": "USD"},
        headers=headers,
    )
    family_id = fam_resp.json()["id"]
    return token, family_id


@pytest.mark.asyncio
async def test_create_budget_success(async_client: AsyncClient):
    """Test creating a new category monthly budget with zero initial spending."""
    token, fam_id = await create_user_and_family(
        async_client, "Budget User 1", "budget1@example.com", "Budget Fam 1"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Retrieve default Grocery category
    cats_resp = await async_client.get("/api/v1/categories?type=expense", headers=headers)
    cats = cats_resp.json()
    grocery = next(c for c in cats if c["name"] == "Grocery")

    payload = {
        "category_id": grocery["id"],
        "amount": "500.00",
        "month": 10,
        "year": 2026,
    }
    resp = await async_client.post("/api/v1/budgets", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["family_id"] == fam_id
    assert data["category_id"] == grocery["id"]
    assert data["category_name"] == "Grocery"
    assert data["amount"] == "500.00"
    assert data["amount_spent"] == "0.00"
    assert data["remaining_amount"] == "500.00"
    assert data["percentage_used"] == "0.00"
    assert data["warning_level"] == "normal"
    assert data["has_warning"] is False
    assert data["is_exceeded"] is False
    assert data["month"] == 10
    assert data["year"] == 2026


@pytest.mark.asyncio
async def test_budget_spent_calculation_and_sql_aggregation(async_client: AsyncClient):
    """
    Test SQL-aggregated spending for budgets:
    - Expenses in the same month/year and category must be summed.
    - Expenses in different months or different categories must NOT be included.
    - Verifies 75% warning threshold.
    """
    token, _ = await create_user_and_family(
        async_client, "Budget User 2", "budget2@example.com", "Budget Fam 2"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch categories
    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    grocery = next(c for c in cats if c["name"] == "Grocery")
    rent = next(c for c in cats if c["name"] == "Rent")

    # Create budget of 1000.00 for Grocery in 10/2026
    b_resp = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": grocery["id"], "amount": "1000.00", "month": 10, "year": 2026},
        headers=headers,
    )
    assert b_resp.status_code == 201
    budget_id = b_resp.json()["id"]

    # 1. Matching expense 1: 300.00 on 2026-10-05 (Grocery)
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "300.00",
            "category_id": grocery["id"],
            "expense_date": "2026-10-05",
            "title": "Grocery trip 1",
        },
        headers=headers,
    )

    # 2. Matching expense 2: 450.00 on 2026-10-20 (Grocery) -> Total = 750.00 (75%)
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "450.00",
            "category_id": grocery["id"],
            "expense_date": "2026-10-20",
            "title": "Grocery trip 2",
        },
        headers=headers,
    )

    # 3. Non-matching expense: 200.00 on 2026-11-05 (different month)
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "200.00",
            "category_id": grocery["id"],
            "expense_date": "2026-11-05",
            "title": "November Grocery",
        },
        headers=headers,
    )

    # 4. Non-matching expense: 600.00 on 2026-10-15 (different category: Rent)
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "600.00",
            "category_id": rent["id"],
            "expense_date": "2026-10-15",
            "title": "October Rent",
        },
        headers=headers,
    )

    # Query the budget
    resp = await async_client.get(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["amount"] == "1000.00"
    assert data["amount_spent"] == "750.00"
    assert data["remaining_amount"] == "250.00"
    assert data["percentage_used"] == "75.00"
    assert data["warning_level"] == "75%"
    assert data["has_warning"] is True
    assert data["is_exceeded"] is False


@pytest.mark.asyncio
async def test_budget_warning_threshold_90_percent(async_client: AsyncClient):
    """Test 90% budget warning trigger when percentage used >= 90% and < 100%."""
    token, _ = await create_user_and_family(
        async_client, "Budget User 3", "budget3@example.com", "Budget Fam 3"
    )
    headers = {"Authorization": f"Bearer {token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    dining = next(c for c in cats if c["name"] == "Dining")

    # Budget of 200.00
    b_resp = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": dining["id"], "amount": "200.00", "month": 10, "year": 2026},
        headers=headers,
    )
    budget_id = b_resp.json()["id"]

    # Expense of 184.00 (92% used)
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "184.00",
            "category_id": dining["id"],
            "expense_date": "2026-10-12",
            "title": "Fine Dining",
        },
        headers=headers,
    )

    resp = await async_client.get(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["amount_spent"] == "184.00"
    assert data["remaining_amount"] == "16.00"
    assert data["percentage_used"] == "92.00"
    assert data["warning_level"] == "90%"
    assert data["has_warning"] is True
    assert data["is_exceeded"] is False


@pytest.mark.asyncio
async def test_budget_warning_threshold_100_plus_percent(async_client: AsyncClient):
    """Test 100%+ budget warning and negative remaining amount when budget is exceeded."""
    token, _ = await create_user_and_family(
        async_client, "Budget User 4", "budget4@example.com", "Budget Fam 4"
    )
    headers = {"Authorization": f"Bearer {token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    fuel = next(c for c in cats if c["name"] == "Fuel")

    # Budget of 100.00
    b_resp = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": fuel["id"], "amount": "100.00", "month": 10, "year": 2026},
        headers=headers,
    )
    budget_id = b_resp.json()["id"]

    # Expense of 115.50 (115.50% used)
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "115.50",
            "category_id": fuel["id"],
            "expense_date": "2026-10-14",
            "title": "Gas Station Fill-up",
        },
        headers=headers,
    )

    resp = await async_client.get(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["amount_spent"] == "115.50"
    assert data["remaining_amount"] == "-15.50"
    assert data["percentage_used"] == "115.50"
    assert data["warning_level"] == "100%+"
    assert data["has_warning"] is True
    assert data["is_exceeded"] is True


@pytest.mark.asyncio
async def test_one_budget_per_family_category_month_year(async_client: AsyncClient):
    """Test constraint: only one budget allowed per family, category, month, and year."""
    token, _ = await create_user_and_family(
        async_client, "Budget User 5", "budget5@example.com", "Budget Fam 5"
    )
    headers = {"Authorization": f"Bearer {token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    grocery = next(c for c in cats if c["name"] == "Grocery")

    # First budget for 10/2026 succeeds
    resp1 = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": grocery["id"], "amount": "400.00", "month": 10, "year": 2026},
        headers=headers,
    )
    assert resp1.status_code == 201

    # Duplicate budget for same category and 10/2026 fails with 409 Conflict
    resp2 = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": grocery["id"], "amount": "450.00", "month": 10, "year": 2026},
        headers=headers,
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["error"]["message"]

    # Same category in different month (11/2026) succeeds
    resp3 = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": grocery["id"], "amount": "450.00", "month": 11, "year": 2026},
        headers=headers,
    )
    assert resp3.status_code == 201


@pytest.mark.asyncio
async def test_budget_amount_must_be_greater_than_zero(async_client: AsyncClient):
    """Test validation: budget amount must be strictly greater than zero."""
    token, _ = await create_user_and_family(
        async_client, "Budget User 6", "budget6@example.com", "Budget Fam 6"
    )
    headers = {"Authorization": f"Bearer {token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    grocery = next(c for c in cats if c["name"] == "Grocery")

    # Zero amount
    resp_zero = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": grocery["id"], "amount": "0.00", "month": 10, "year": 2026},
        headers=headers,
    )
    assert resp_zero.status_code in (400, 422)

    # Negative amount
    resp_neg = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": grocery["id"], "amount": "-50.00", "month": 10, "year": 2026},
        headers=headers,
    )
    assert resp_neg.status_code in (400, 422)


@pytest.mark.asyncio
async def test_category_must_belong_to_family(async_client: AsyncClient):
    """Test validation: category must be accessible to user's family."""
    token_a, _ = await create_user_and_family(
        async_client, "User 7A", "user7a@example.com", "Family 7A"
    )
    token_b, _ = await create_user_and_family(
        async_client, "User 7B", "user7b@example.com", "Family 7B"
    )

    # Family B creates custom category
    cat_b = (
        await async_client.post(
            "/api/v1/categories",
            json={"name": "Family B Special Expense", "type": "expense"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
    ).json()

    # Family A tries to create budget using Family B's category
    resp = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": cat_b["id"], "amount": "300.00", "month": 10, "year": 2026},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 400
    assert "Category not found or does not belong to your family" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_category_cannot_be_income_type(async_client: AsyncClient):
    """Test validation: budgets can only be created for expense categories."""
    token, _ = await create_user_and_family(
        async_client, "User 8", "user8@example.com", "Family 8"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch income category "Salary"
    income_cats = (
        await async_client.get("/api/v1/categories?type=income", headers=headers)
    ).json()
    salary = next(c for c in income_cats if c["name"] == "Salary")

    resp = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": salary["id"], "amount": "5000.00", "month": 10, "year": 2026},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Budgets can only be set for expense categories" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_only_family_members_can_access_budget(async_client: AsyncClient):
    """Test strict multi-tenant isolation: other families cannot view, update, or delete budgets."""
    token_a, _ = await create_user_and_family(
        async_client, "Family 9A User", "user9a@example.com", "Family 9A"
    )
    token_b, _ = await create_user_and_family(
        async_client, "Family 9B User", "user9b@example.com", "Family 9B"
    )

    cats = (
        await async_client.get(
            "/api/v1/categories?type=expense",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ).json()

    # Family A creates budget
    budget_a = (
        await async_client.post(
            "/api/v1/budgets",
            json={"category_id": cats[0]["id"], "amount": "800.00", "month": 10, "year": 2026},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ).json()

    # Family B tries to GET Family A's budget -> 404
    get_resp = await async_client.get(
        f"/api/v1/budgets/{budget_a['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_resp.status_code == 404

    # Family B tries to PUT Family A's budget -> 404
    put_resp = await async_client.put(
        f"/api/v1/budgets/{budget_a['id']}",
        json={"amount": "999.00"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert put_resp.status_code == 404

    # Family B tries to DELETE Family A's budget -> 404
    del_resp = await async_client.delete(
        f"/api/v1/budgets/{budget_a['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_budget_crud_lifecycle(async_client: AsyncClient):
    """Test full CRUD lifecycle for budgets: Create, Read, Update, Delete."""
    token, _ = await create_user_and_family(
        async_client, "Lifecycle User", "lifecycle.budget@example.com", "Lifecycle Fam"
    )
    headers = {"Authorization": f"Bearer {token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    internet = next(c for c in cats if c["name"] == "Internet")

    # 1. Create
    create_resp = await async_client.post(
        "/api/v1/budgets",
        json={"category_id": internet["id"], "amount": "70.00", "month": 10, "year": 2026},
        headers=headers,
    )
    assert create_resp.status_code == 201
    budget_id = create_resp.json()["id"]

    # 2. Read single
    read_resp = await async_client.get(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["amount"] == "70.00"

    # 3. Update amount
    update_resp = await async_client.put(
        f"/api/v1/budgets/{budget_id}",
        json={"amount": "85.00"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["amount"] == "85.00"

    # 4. List budgets
    list_resp = await async_client.get("/api/v1/budgets?month=10&year=2026", headers=headers)
    assert list_resp.status_code == 200
    budgets = list_resp.json()
    assert any(b["id"] == budget_id for b in budgets)

    # 5. Delete
    delete_resp = await async_client.delete(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["budget_id"] == budget_id

    # 6. Verify deleted
    get_again = await async_client.get(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert get_again.status_code == 404
