from datetime import date
import uuid
import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.scripts.seed_categories import seed_default_categories


EXPECTED_DEFAULT_EXPENSES = [
    "Grocery",
    "Rent",
    "Electricity",
    "Internet",
    "Fuel",
    "Shopping",
    "Dining",
    "Medical",
    "Education",
    "Travel",
    "Entertainment",
    "Insurance",
    "EMI",
    "Household",
    "Other",
]

EXPECTED_DEFAULT_INCOMES = [
    "Salary",
    "Freelance",
    "Business",
    "Bonus",
    "Interest",
    "Investment",
    "Gift",
    "Other",
]


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
async def test_list_categories_default_seeded(async_client: AsyncClient):
    """Test listing categories returns all 23 default system categories with correct metadata."""
    token, _ = await create_user_and_family(
        async_client, "Cat User", "cat.user@example.com", "Cat Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await async_client.get("/api/v1/categories", headers=headers)
    assert resp.status_code == 200
    categories = resp.json()

    # Total 15 expense + 8 income = 23 default categories
    assert len(categories) == 23

    # All defaults must have family_id=None and is_default=True
    for cat in categories:
        assert cat["family_id"] is None
        assert cat["is_default"] is True

    # Check all expense category names
    expense_names = [c["name"] for c in categories if c["type"] == "expense"]
    for expected in EXPECTED_DEFAULT_EXPENSES:
        assert expected in expense_names

    # Check all income category names
    income_names = [c["name"] for c in categories if c["type"] == "income"]
    for expected in EXPECTED_DEFAULT_INCOMES:
        assert expected in income_names


@pytest.mark.asyncio
async def test_list_categories_filter_by_type(async_client: AsyncClient):
    """Test filtering categories by type (case-insensitive) and validation."""
    token, _ = await create_user_and_family(
        async_client, "Filter User", "filter.user@example.com", "Filter Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Filter expense (lowercase)
    exp_resp = await async_client.get("/api/v1/categories?type=expense", headers=headers)
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert len(exp_data) == 15
    assert all(c["type"] in ("expense", "both") for c in exp_data)

    # Filter income (uppercase)
    inc_resp = await async_client.get("/api/v1/categories?type=INCOME", headers=headers)
    assert inc_resp.status_code == 200
    inc_data = inc_resp.json()
    assert len(inc_data) == 8
    assert all(c["type"] in ("income", "both") for c in inc_data)

    # Invalid type filter
    bad_resp = await async_client.get("/api/v1/categories?type=unknown", headers=headers)
    assert bad_resp.status_code == 400


@pytest.mark.asyncio
async def test_create_custom_category_success(async_client: AsyncClient):
    """Test creating a custom family category."""
    token, fam_id = await create_user_and_family(
        async_client, "Custom Cat User", "custom.cat@example.com", "Custom Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Pet Care",
        "icon": "pets",
        "color": "#795548",
        "type": "EXPENSE",
    }
    resp = await async_client.post("/api/v1/categories", json=payload, headers=headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Pet Care"
    assert created["icon"] == "pets"
    assert created["color"] == "#795548"
    assert created["type"] == "expense"
    assert created["is_default"] is False
    assert created["family_id"] == fam_id

    # Verify it now appears in listing
    list_resp = await async_client.get("/api/v1/categories", headers=headers)
    assert list_resp.status_code == 200
    all_cats = list_resp.json()
    assert len(all_cats) == 24  # 23 default + 1 custom
    assert any(c["name"] == "Pet Care" and c["id"] == created["id"] for c in all_cats)


@pytest.mark.asyncio
async def test_create_custom_category_duplicate_rejected(async_client: AsyncClient):
    """Test duplicate category names (within family or colliding with default) are rejected."""
    token, _ = await create_user_and_family(
        async_client, "Dup Cat User", "dup.cat@example.com", "Dup Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Attempting to create category that collides with default "Grocery" expense
    resp = await async_client.post(
        "/api/v1/categories",
        json={"name": "Grocery", "type": "expense"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["error"]["message"]

    # Create custom "Subscriptions"
    resp1 = await async_client.post(
        "/api/v1/categories",
        json={"name": "Subscriptions", "type": "expense"},
        headers=headers,
    )
    assert resp1.status_code == 201

    # Attempt duplicate custom "Subscriptions"
    resp2 = await async_client.post(
        "/api/v1/categories",
        json={"name": "subscriptions", "type": "expense"},
        headers=headers,
    )
    assert resp2.status_code == 409

@pytest.mark.asyncio
async def test_update_custom_category_success(async_client: AsyncClient):
    """Test updating a family's custom category."""
    token, _ = await create_user_and_family(
        async_client, "Update Cat User", "update.cat@example.com", "Update Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Create custom category
    cat_resp = await async_client.post(
        "/api/v1/categories",
        json={"name": "Gadgets", "icon": "devices", "color": "#000000", "type": "expense"},
        headers=headers,
    )
    cat_id = cat_resp.json()["id"]

    # Update category
    upd_resp = await async_client.put(
        f"/api/v1/categories/{cat_id}",
        json={"name": "Electronics & Gadgets", "color": "#2196F3"},
        headers=headers,
    )
    assert upd_resp.status_code == 200
    updated = upd_resp.json()
    assert updated["id"] == cat_id
    assert updated["name"] == "Electronics & Gadgets"
    assert updated["color"] == "#2196F3"
    assert updated["icon"] == "devices"  # Preserved unchanged


@pytest.mark.asyncio
async def test_cannot_update_default_category(async_client: AsyncClient):
    """Test modifying a system default category is prohibited (HTTP 403)."""
    token, _ = await create_user_and_family(
        async_client, "NoEdit Default", "noedit@example.com", "Default Edit Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Find default category "Salary"
    list_resp = await async_client.get("/api/v1/categories?type=income", headers=headers)
    salary_cat = next(c for c in list_resp.json() if c["name"] == "Salary")

    upd_resp = await async_client.put(
        f"/api/v1/categories/{salary_cat['id']}",
        json={"name": "Modified Salary"},
        headers=headers,
    )
    assert upd_resp.status_code == 403
    assert "System default categories cannot be modified" in upd_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_cannot_update_other_family_category(async_client: AsyncClient):
    """Test updating another family's custom category is not permitted (HTTP 404)."""
    token_a, _ = await create_user_and_family(
        async_client, "Fam A User", "fama@example.com", "Family A"
    )
    token_b, _ = await create_user_and_family(
        async_client, "Fam B User", "famb@example.com", "Family B"
    )

    # Family A creates custom category
    cat_a = (
        await async_client.post(
            "/api/v1/categories",
            json={"name": "Secret A Category", "type": "expense"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ).json()

    # Family B tries to update Family A's category
    upd_resp = await async_client.put(
        f"/api/v1/categories/{cat_a['id']}",
        json={"name": "Hacked Category"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert upd_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_custom_category_success(async_client: AsyncClient):
    """Test deleting an unused custom category succeeds."""
    token, _ = await create_user_and_family(
        async_client, "Delete Cat User", "del.cat@example.com", "Delete Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Create category
    cat = (
        await async_client.post(
            "/api/v1/categories",
            json={"name": "Temporary", "type": "expense"},
            headers=headers,
        )
    ).json()

    # Delete category
    del_resp = await async_client.delete(f"/api/v1/categories/{cat['id']}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["category_id"] == cat["id"]

    # Verify category is gone
    list_resp = await async_client.get("/api/v1/categories", headers=headers)
    assert not any(c["id"] == cat["id"] for c in list_resp.json())


@pytest.mark.asyncio
async def test_cannot_delete_default_category(async_client: AsyncClient):
    """Test system default categories cannot be deleted (HTTP 403)."""
    token, _ = await create_user_and_family(
        async_client, "NoDel Default", "nodel@example.com", "No Del Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Find default category "Grocery"
    list_resp = await async_client.get("/api/v1/categories", headers=headers)
    grocery = next(c for c in list_resp.json() if c["name"] == "Grocery")

    del_resp = await async_client.delete(f"/api/v1/categories/{grocery['id']}", headers=headers)
    assert del_resp.status_code == 403
    assert "System default categories cannot be deleted" in del_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_cannot_delete_other_family_category(async_client: AsyncClient):
    """Test deleting another family's custom category returns 404."""
    token_a, _ = await create_user_and_family(
        async_client, "Fam A2 User", "fama2@example.com", "Family A2"
    )
    token_b, _ = await create_user_and_family(
        async_client, "Fam B2 User", "famb2@example.com", "Family B2"
    )

    cat_a = (
        await async_client.post(
            "/api/v1/categories",
            json={"name": "Family A Private", "type": "expense"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
    ).json()

    del_resp = await async_client.delete(
        f"/api/v1/categories/{cat_a['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_category_in_use_by_expense(async_client: AsyncClient):
    """Test custom category in active use by an expense cannot be deleted (HTTP 400)."""
    token, _ = await create_user_and_family(
        async_client, "InUse Expense", "inuse.exp@example.com", "In Use Exp Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Create custom category
    cat = (
        await async_client.post(
            "/api/v1/categories",
            json={"name": "Gym & Fitness", "type": "expense"},
            headers=headers,
        )
    ).json()

    # Create expense with this category
    exp_resp = await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "50.00",
            "category_id": cat["id"],
            "expense_date": str(date.today()),
            "title": "Gym Monthly Pass",
        },
        headers=headers,
    )
    assert exp_resp.status_code == 201

    # Attempt to delete category
    del_resp = await async_client.delete(f"/api/v1/categories/{cat['id']}", headers=headers)
    assert del_resp.status_code == 400
    assert "associated with 1 expense(s)" in del_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_cannot_delete_category_in_use_by_income(async_client: AsyncClient):
    """Test custom category in active use by income cannot be deleted (HTTP 400)."""
    token, _ = await create_user_and_family(
        async_client, "InUse Income", "inuse.inc@example.com", "In Use Inc Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Create custom income category
    cat = (
        await async_client.post(
            "/api/v1/categories",
            json={"name": "Book Royalties", "type": "income"},
            headers=headers,
        )
    ).json()

    # Create income with this category
    inc_resp = await async_client.post(
        "/api/v1/income",
        json={
            "amount": "800.00",
            "category_id": cat["id"],
            "income_date": str(date.today()),
            "title": "Q3 Book Royalty",
        },
        headers=headers,
    )
    assert inc_resp.status_code == 201

    # Attempt to delete category
    del_resp = await async_client.delete(f"/api/v1/categories/{cat['id']}", headers=headers)
    assert del_resp.status_code == 400
    assert "associated with 1 income(s)" in del_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_seed_categories_idempotent():
    """Test that seed_default_categories can be executed multiple times without errors or duplicate rows."""
    async with AsyncSessionLocal() as session:
        # First execution (already seeded in fixture)
        created1, existing1 = await seed_default_categories(session)
        assert created1 == 0
        assert existing1 == 23

        # Second execution
        created2, existing2 = await seed_default_categories(session)
        assert created2 == 0
        assert existing2 == 23
