from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient


async def create_user_and_family(client: AsyncClient, name: str, email: str, fam_name: str) -> tuple[str, str]:
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
async def test_create_expense_success(async_client: AsyncClient):
    """Test creating an expense with Decimal precision and auto-assigned payer."""
    token, _ = await create_user_and_family(
        async_client, "John Grocer", "grocer@example.com", "Grocer Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Retrieve seeded categories
    cat_resp = await async_client.get("/api/v1/categories", headers=headers)
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    assert len(categories) > 0
    cat_id = categories[0]["id"]
    cat_name = categories[0]["name"]

    payload = {
        "amount": "145.80",
        "category_id": cat_id,
        "expense_date": str(date.today()),
        "payment_method": "credit_card",
        "title": "Supermarket Grocery Haul",
        "description": "Vegetables, fruits, and dairy",
        "is_shared": True,
    }
    response = await async_client.post("/api/v1/expenses", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == "145.80"
    assert data["currency"] == "USD"
    assert data["title"] == "Supermarket Grocery Haul"
    assert data["category_name"] == cat_name
    assert data["paid_by_name"] == "John Grocer"
    assert data["is_shared"] is True


@pytest.mark.asyncio
async def test_create_expense_with_spouse_payer(async_client: AsyncClient):
    """Test creating an expense designating another active family member as paid_by."""
    h_token, fam_id = await create_user_and_family(
        async_client, "Husband", "husband.payer@example.com", "Payer Family"
    )
    h_headers = {"Authorization": f"Bearer {h_token}"}

    # Invite Wife
    inv_resp = await async_client.post(
        "/api/v1/families/invite",
        json={"invited_email": "wife.payer@example.com"},
        headers=h_headers,
    )
    token_str = inv_resp.json()["token"]

    # Register Wife and accept
    w_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"full_name": "Wife", "email": "wife.payer@example.com", "password": "Password123!"},
    )
    w_token = w_resp.json()["access_token"]
    w_headers = {"Authorization": f"Bearer {w_token}"}
    await async_client.post("/api/v1/families/invite/accept", json={"token": token_str}, headers=w_headers)

    # Get wife user ID from /users/me
    w_profile = (await async_client.get("/api/v1/users/me", headers=w_headers)).json()
    wife_id = w_profile["id"]

    # Get category
    cats = (await async_client.get("/api/v1/categories", headers=h_headers)).json()

    # Husband records expense paid by Wife
    exp_resp = await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "89.50",
            "category_id": cats[0]["id"],
            "expense_date": str(date.today()),
            "title": "Dinner with Friends",
            "paid_by": wife_id,
        },
        headers=h_headers,
    )
    assert exp_resp.status_code == 201
    assert exp_resp.json()["paid_by"] == wife_id
    assert exp_resp.json()["paid_by_name"] == "Wife"
    assert exp_resp.json()["created_by_name"] == "Husband"


@pytest.mark.asyncio
async def test_foreign_category_rejected(async_client: AsyncClient):
    """Test cannot create expense using another family's custom category."""
    token_a, _ = await create_user_and_family(async_client, "User A", "user.a@example.com", "Fam A")
    token_b, _ = await create_user_and_family(async_client, "User B", "user.b@example.com", "Fam B")

    # Family B creates custom category
    cat_resp = await async_client.post(
        "/api/v1/categories",
        json={"name": "Family B Special", "type": "expense"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    cat_b_id = cat_resp.json()["id"]

    # Family A tries to use Family B's category
    exp_resp = await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "20.00",
            "category_id": cat_b_id,
            "expense_date": str(date.today()),
            "title": "Illicit Category Usage",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert exp_resp.status_code == 400


@pytest.mark.asyncio
async def test_foreign_payer_rejected(async_client: AsyncClient):
    """Test cannot specify a paid_by user from a different family."""
    token_a, _ = await create_user_and_family(async_client, "User A", "user.a2@example.com", "Fam A2")
    token_b, _ = await create_user_and_family(async_client, "User B", "user.b2@example.com", "Fam B2")

    user_b_id = (
        await async_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token_b}"})
    ).json()["id"]
    cat_id = (
        await async_client.get("/api/v1/categories", headers={"Authorization": f"Bearer {token_a}"})
    ).json()[0]["id"]

    # Family A attempts to set paid_by = user_b
    exp_resp = await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "30.00",
            "category_id": cat_id,
            "expense_date": str(date.today()),
            "title": "Foreign Payer",
            "paid_by": user_b_id,
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert exp_resp.status_code == 400


@pytest.mark.asyncio
async def test_expense_crud_lifecycle(async_client: AsyncClient):
    """Test GET, PUT, and DELETE operations on a single expense."""
    token, _ = await create_user_and_family(async_client, "CRUD User", "crud@example.com", "CRUD Fam")
    headers = {"Authorization": f"Bearer {token}"}
    cats = (await async_client.get("/api/v1/categories", headers=headers)).json()

    # 1. Create
    create_resp = await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "50.00",
            "category_id": cats[0]["id"],
            "expense_date": str(date.today()),
            "title": "Initial Title",
        },
        headers=headers,
    )
    expense_id = create_resp.json()["id"]

    # 2. GET by ID
    get_resp = await async_client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Initial Title"

    # 3. PUT
    put_resp = await async_client.put(
        f"/api/v1/expenses/{expense_id}",
        json={"amount": "75.25", "title": "Updated Title"},
        headers=headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["amount"] == "75.25"
    assert put_resp.json()["title"] == "Updated Title"

    # 4. DELETE
    del_resp = await async_client.delete(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert del_resp.status_code == 200

    # 5. Verify 404 after delete
    get_again = await async_client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert get_again.status_code == 404


@pytest.mark.asyncio
async def test_strict_multi_tenant_isolation(async_client: AsyncClient):
    """Test Family B cannot view or modify Family A's expenses."""
    token_a, _ = await create_user_and_family(async_client, "A User", "iso.a@example.com", "Fam A")
    token_b, _ = await create_user_and_family(async_client, "B User", "iso.b@example.com", "Fam B")

    cat_id = (
        await async_client.get("/api/v1/categories", headers={"Authorization": f"Bearer {token_a}"})
    ).json()[0]["id"]
    create_resp = await async_client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "category_id": cat_id, "expense_date": str(date.today()), "title": "Secret A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    expense_a_id = create_resp.json()["id"]

    # Family B tries to GET Family A's expense
    b_get = await async_client.get(
        f"/api/v1/expenses/{expense_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert b_get.status_code == 404

    # Family B tries to DELETE Family A's expense
    b_del = await async_client.delete(
        f"/api/v1/expenses/{expense_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert b_del.status_code == 404


@pytest.mark.asyncio
async def test_pagination_and_total_amount(async_client: AsyncClient):
    """Test pagination, total count, and total amount calculation."""
    token, _ = await create_user_and_family(async_client, "Page User", "page@example.com", "Page Fam")
    headers = {"Authorization": f"Bearer {token}"}
    cats = (await async_client.get("/api/v1/categories", headers=headers)).json()
    cat_id = cats[0]["id"]

    # Create 5 expenses: 10.00, 20.00, 30.00, 40.00, 50.00 -> Sum = 150.00
    for i, amt in enumerate(["10.00", "20.00", "30.00", "40.00", "50.00"]):
        exp_date = str(date.today() - timedelta(days=i))
        await async_client.post(
            "/api/v1/expenses",
            json={"amount": amt, "category_id": cat_id, "expense_date": exp_date, "title": f"Expense {i}"},
            headers=headers,
        )

    # Page 1, size 2
    resp = await async_client.get("/api/v1/expenses?page=1&page_size=2", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["total_pages"] == 3
    assert data["total_amount"] == "150.00"

    # Page 3, size 2 (should have 1 item)
    resp3 = await async_client.get("/api/v1/expenses?page=3&page_size=2", headers=headers)
    assert len(resp3.json()["items"]) == 1


@pytest.mark.asyncio
async def test_filtering_and_searching(async_client: AsyncClient):
    """Test searching by keyword and filtering by date range, payment method, shared status."""
    token, _ = await create_user_and_family(async_client, "Filter User", "filter@example.com", "Filter Fam")
    headers = {"Authorization": f"Bearer {token}"}
    cats = (await async_client.get("/api/v1/categories", headers=headers)).json()

    today = date.today()
    # Exp 1: Coffee, cash, today, personal
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "5.50",
            "category_id": cats[0]["id"],
            "expense_date": str(today),
            "payment_method": "cash",
            "title": "Morning Coffee",
            "is_shared": False,
        },
        headers=headers,
    )

    # Exp 2: Electricity, bank_transfer, 5 days ago, shared
    await async_client.post(
        "/api/v1/expenses",
        json={
            "amount": "120.00",
            "category_id": cats[0]["id"],
            "expense_date": str(today - timedelta(days=5)),
            "payment_method": "bank_transfer",
            "title": "Electricity Bill",
            "is_shared": True,
        },
        headers=headers,
    )

    # Search keyword
    s_resp = await async_client.get("/api/v1/expenses?search=coffee", headers=headers)
    assert s_resp.json()["total"] == 1
    assert s_resp.json()["items"][0]["title"] == "Morning Coffee"

    # Filter payment method
    pm_resp = await async_client.get("/api/v1/expenses?payment_method=bank_transfer", headers=headers)
    assert pm_resp.json()["total"] == 1
    assert pm_resp.json()["items"][0]["title"] == "Electricity Bill"

    # Filter shared = False
    sh_resp = await async_client.get("/api/v1/expenses?is_shared=false", headers=headers)
    assert sh_resp.json()["total"] == 1
    assert sh_resp.json()["items"][0]["title"] == "Morning Coffee"

    # Filter date range (yesterday to tomorrow -> only Coffee matches)
    dt_resp = await async_client.get(
        f"/api/v1/expenses?from_date={today - timedelta(days=1)}&to_date={today + timedelta(days=1)}",
        headers=headers,
    )
    assert dt_resp.json()["total"] == 1
    assert dt_resp.json()["items"][0]["title"] == "Morning Coffee"
