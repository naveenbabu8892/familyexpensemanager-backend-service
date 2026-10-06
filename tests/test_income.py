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
async def test_create_income_success(async_client: AsyncClient):
    """Test creating an income record with Decimal precision and auto-assigned recipient."""
    token, _ = await create_user_and_family(
        async_client, "Alice Earner", "earner@example.com", "Earner Family"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Retrieve seeded categories (filtered by income)
    cat_resp = await async_client.get("/api/v1/categories?type=income", headers=headers)
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    assert len(categories) > 0
    salary_cat = next((c for c in categories if c["name"] == "Salary"), categories[0])

    payload = {
        "amount": "5200.50",
        "category_id": salary_cat["id"],
        "income_date": str(date.today()),
        "title": "Monthly Consulting Retainer",
        "description": "Tech advisory retainer for client XYZ",
    }
    response = await async_client.post("/api/v1/income", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == "5200.50"
    assert data["currency"] == "USD"
    assert data["title"] == "Monthly Consulting Retainer"
    assert data["category_name"] == salary_cat["name"]
    assert data["received_by_name"] == "Alice Earner"


@pytest.mark.asyncio
async def test_create_income_with_spouse_as_recipient(async_client: AsyncClient):
    """Test recording an income received by another active family member."""
    h_token, fam_id = await create_user_and_family(
        async_client, "Husband Income", "h.income@example.com", "Dual Income Family"
    )
    h_headers = {"Authorization": f"Bearer {h_token}"}

    # Invite spouse
    inv_resp = await async_client.post(
        "/api/v1/families/invite",
        json={"invited_email": "w.income@example.com"},
        headers=h_headers,
    )
    token_str = inv_resp.json()["token"]

    # Register spouse and accept invitation
    w_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"full_name": "Wife Income", "email": "w.income@example.com", "password": "Password123!"},
    )
    w_token = w_resp.json()["access_token"]
    w_headers = {"Authorization": f"Bearer {w_token}"}
    await async_client.post("/api/v1/families/invite/accept", json={"token": token_str}, headers=w_headers)

    w_profile = (await async_client.get("/api/v1/users/me", headers=w_headers)).json()
    wife_id = w_profile["id"]

    # Husband records income received by Wife
    inc_resp = await async_client.post(
        "/api/v1/income",
        json={
            "amount": "3400.00",
            "income_date": str(date.today()),
            "title": "Wife Quarterly Bonus",
            "received_by": wife_id,
        },
        headers=h_headers,
    )
    assert inc_resp.status_code == 201
    assert inc_resp.json()["received_by"] == wife_id
    assert inc_resp.json()["received_by_name"] == "Wife Income"


@pytest.mark.asyncio
async def test_foreign_recipient_rejected(async_client: AsyncClient):
    """Test cannot set received_by to a member of a different family."""
    token_a, _ = await create_user_and_family(async_client, "User A", "user.inc.a@example.com", "Fam A")
    token_b, _ = await create_user_and_family(async_client, "User B", "user.inc.b@example.com", "Fam B")

    user_b_id = (
        await async_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token_b}"})
    ).json()["id"]

    # Family A attempts to record income for User B
    resp = await async_client.post(
        "/api/v1/income",
        json={
            "amount": "1000.00",
            "income_date": str(date.today()),
            "title": "Foreign Recipient",
            "received_by": user_b_id,
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_income_crud_lifecycle(async_client: AsyncClient):
    """Test GET, PUT, and DELETE operations for an income entry."""
    token, _ = await create_user_and_family(async_client, "CRUD Earner", "crud.inc@example.com", "CRUD Fam")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create
    create_resp = await async_client.post(
        "/api/v1/income",
        json={
            "amount": "2000.00",
            "income_date": str(date.today()),
            "title": "Freelance Milestone 1",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    income_id = create_resp.json()["id"]

    # 2. GET by ID
    get_resp = await async_client.get(f"/api/v1/income/{income_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Freelance Milestone 1"

    # 3. PUT update
    put_resp = await async_client.put(
        f"/api/v1/income/{income_id}",
        json={"amount": "2500.00", "title": "Freelance Milestone 1 (Revised)"},
        headers=headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["amount"] == "2500.00"
    assert put_resp.json()["title"] == "Freelance Milestone 1 (Revised)"

    # 4. DELETE
    del_resp = await async_client.delete(f"/api/v1/income/{income_id}", headers=headers)
    assert del_resp.status_code == 200

    # 5. Verify 404
    get_again = await async_client.get(f"/api/v1/income/{income_id}", headers=headers)
    assert get_again.status_code == 404


@pytest.mark.asyncio
async def test_income_multi_tenant_isolation(async_client: AsyncClient):
    """Test Family B cannot view or delete Family A's income."""
    token_a, _ = await create_user_and_family(async_client, "Earner A", "iso.inc.a@example.com", "Fam A")
    token_b, _ = await create_user_and_family(async_client, "Earner B", "iso.inc.b@example.com", "Fam B")

    create_resp = await async_client.post(
        "/api/v1/income",
        json={"amount": "5000.00", "income_date": str(date.today()), "title": "Family A Secret Income"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    income_a_id = create_resp.json()["id"]

    # Family B tries to GET Family A's income
    b_get = await async_client.get(
        f"/api/v1/income/{income_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert b_get.status_code == 404

    # Family B tries to DELETE Family A's income
    b_del = await async_client.delete(
        f"/api/v1/income/{income_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert b_del.status_code == 404


@pytest.mark.asyncio
async def test_list_income_pagination_and_total_amount(async_client: AsyncClient):
    """Test pagination, total records count, and sum amount calculation."""
    token, _ = await create_user_and_family(async_client, "Page Earner", "page.inc@example.com", "Page Fam")
    headers = {"Authorization": f"Bearer {token}"}

    # Create 4 entries: 1000.00, 2000.00, 3000.00, 4000.00 = Sum 10000.00
    for i, amt in enumerate(["1000.00", "2000.00", "3000.00", "4000.00"]):
        inc_date = str(date.today() - timedelta(days=i))
        await async_client.post(
            "/api/v1/income",
            json={"amount": amt, "income_date": inc_date, "title": f"Income {i}"},
            headers=headers,
        )

    # Page 1, size 2
    resp = await async_client.get("/api/v1/income?page=1&page_size=2", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 4
    assert data["total_pages"] == 2
    assert data["total_amount"] == "10000.00"


@pytest.mark.asyncio
async def test_list_income_date_and_person_filtering(async_client: AsyncClient):
    """Test date range and person filtering."""
    token, _ = await create_user_and_family(async_client, "Filter Earner", "filt.inc@example.com", "Filt Fam")
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    # Income 1: Today
    await async_client.post(
        "/api/v1/income",
        json={"amount": "300.00", "income_date": str(today), "title": "Today Gig"},
        headers=headers,
    )

    # Income 2: 10 days ago
    await async_client.post(
        "/api/v1/income",
        json={"amount": "700.00", "income_date": str(today - timedelta(days=10)), "title": "Old Gig"},
        headers=headers,
    )

    # Filter date range (yesterday to tomorrow -> only Today Gig matches)
    dt_resp = await async_client.get(
        f"/api/v1/income?from_date={today - timedelta(days=1)}&to_date={today + timedelta(days=1)}",
        headers=headers,
    )
    assert dt_resp.status_code == 200
    assert dt_resp.json()["total"] == 1
    assert dt_resp.json()["items"][0]["title"] == "Today Gig"
    assert dt_resp.json()["total_amount"] == "300.00"
