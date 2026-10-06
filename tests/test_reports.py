from datetime import date
from decimal import Decimal
import pytest
from httpx import AsyncClient


async def create_family_with_spouse(
    client: AsyncClient,
) -> tuple[str, str, str, str]:
    """
    Helper to register Husband, create family, invite Wife, register Wife, and accept invite.
    Returns (husband_token, wife_token, family_id, wife_id).
    """
    # 1. Register Husband
    h_resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Husband Alpha", "email": "husband.alpha@example.com", "password": "Password123!"},
    )
    h_token = h_resp.json()["access_token"]
    h_headers = {"Authorization": f"Bearer {h_token}"}

    # 2. Husband creates family
    fam_resp = await client.post(
        "/api/v1/families",
        json={"name": "Alpha Family", "currency": "USD"},
        headers=h_headers,
    )
    fam_id = fam_resp.json()["id"]

    # 3. Husband invites Wife
    inv_resp = await client.post(
        "/api/v1/families/invite",
        json={"invited_email": "wife.alpha@example.com"},
        headers=h_headers,
    )
    invite_token = inv_resp.json()["token"]

    # 4. Register Wife
    w_resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Wife Alpha", "email": "wife.alpha@example.com", "password": "Password123!"},
    )
    w_token = w_resp.json()["access_token"]
    w_headers = {"Authorization": f"Bearer {w_token}"}
    wife_id = (await client.get("/api/v1/users/me", headers=w_headers)).json()["id"]

    # 5. Wife accepts invite
    await client.post(
        "/api/v1/families/invite/accept",
        json={"token": invite_token},
        headers=w_headers,
    )

    return h_token, w_token, fam_id, wife_id


@pytest.mark.asyncio
async def test_dashboard_metrics_and_calculations(async_client: AsyncClient):
    """
    Test consolidated dashboard endpoint:
    - Total income
    - Total expenses
    - Remaining balance & savings rate
    - Shared vs personal expenses
    - My expenses vs spouse expenses (perspective-aware)
    - Budget status summary
    - Recent transactions feed
    """
    h_token, w_token, fam_id, wife_id = await create_family_with_spouse(async_client)
    h_headers = {"Authorization": f"Bearer {h_token}"}
    w_headers = {"Authorization": f"Bearer {w_token}"}

    # Get categories
    cats = (await async_client.get("/api/v1/categories", headers=h_headers)).json()
    salary = next(c for c in cats if c["name"] == "Salary")
    freelance = next(c for c in cats if c["name"] == "Freelance")
    rent = next(c for c in cats if c["name"] == "Rent")
    grocery = next(c for c in cats if c["name"] == "Grocery")
    shopping = next(c for c in cats if c["name"] == "Shopping")

    # 1. Incomes:
    # Husband salary 6000.00 in 2026-10-01
    await async_client.post(
        "/api/v1/income",
        json={"amount": "6000.00", "category_id": salary["id"], "income_date": "2026-10-01", "title": "Husband Salary"},
        headers=h_headers,
    )
    # Wife freelance 4000.00 in 2026-10-02
    await async_client.post(
        "/api/v1/income",
        json={"amount": "4000.00", "category_id": freelance["id"], "income_date": "2026-10-02", "title": "Wife Consulting"},
        headers=w_headers,
    )
    # Total income = 10000.00

    # 2. Expenses:
    # Husband shared Rent 1200.00
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "1200.00", "category_id": rent["id"], "expense_date": "2026-10-05", "title": "Apartment Rent", "is_shared": True},
        headers=h_headers,
    )
    # Husband personal Gadgets 300.00
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "300.00", "category_id": shopping["id"], "expense_date": "2026-10-06", "title": "Mechanical Keyboard", "is_shared": False},
        headers=h_headers,
    )
    # Wife shared Grocery 500.00
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "500.00", "category_id": grocery["id"], "expense_date": "2026-10-08", "title": "Weekly Groceries", "is_shared": True},
        headers=w_headers,
    )
    # Wife personal Shopping 200.00
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "200.00", "category_id": shopping["id"], "expense_date": "2026-10-10", "title": "New Dress", "is_shared": False},
        headers=w_headers,
    )
    # Total expenses = 1200 + 300 + 500 + 200 = 2200.00
    # Shared = 1200 + 500 = 1700.00
    # Personal = 300 + 200 = 500.00

    # 3. Budget:
    # Create Grocery budget of 600.00 for 10/2026
    await async_client.post(
        "/api/v1/budgets",
        json={"category_id": grocery["id"], "amount": "600.00", "month": 10, "year": 2026},
        headers=h_headers,
    )

    # 4. Query Dashboard from HUSBAND perspective
    h_dash_resp = await async_client.get(
        "/api/v1/dashboard?month=10&year=2026",
        headers=h_headers,
    )
    assert h_dash_resp.status_code == 200
    h_data = h_dash_resp.json()

    assert h_data["currency"] == "USD"
    assert h_data["total_income"] == "10000.00"
    assert h_data["total_expenses"] == "2200.00"
    assert h_data["remaining_balance"] == "7800.00"
    assert h_data["savings_rate"] == "78.00"
    assert h_data["shared_expenses"] == "1700.00"
    assert h_data["personal_expenses"] == "500.00"
    # Husband paid 1200 + 300 = 1500; spouse paid 500 + 200 = 700
    assert h_data["my_expenses"] == "1500.00"
    assert h_data["spouse_expenses"] == "700.00"

    # Budget summary check
    bs = h_data["budget_status"]
    assert bs["total_budget"] == "600.00"
    assert bs["total_spent"] == "500.00"
    assert bs["total_remaining"] == "100.00"
    assert bs["percentage_used"] == "83.33"
    assert bs["has_warning"] is True
    assert bs["is_exceeded"] is False
    assert bs["active_budgets_count"] == 1

    # Recent transactions
    recent = h_data["recent_transactions"]
    assert len(recent) == 5  # capped at 5
    assert all("id" in t and "amount" in t and "type" in t for t in recent)

    # 5. Query Dashboard from WIFE perspective
    w_dash_resp = await async_client.get(
        "/api/v1/dashboard?month=10&year=2026",
        headers=w_headers,
    )
    assert w_dash_resp.status_code == 200
    w_data = w_dash_resp.json()
    # Wife paid 700; spouse (husband) paid 1500
    assert w_data["my_expenses"] == "700.00"
    assert w_data["spouse_expenses"] == "1500.00"


@pytest.mark.asyncio
async def test_monthly_report_calculations(async_client: AsyncClient):
    """Test annual monthly performance report with PostgreSQL EXTRACT aggregation."""
    h_token, _, _, _ = await create_family_with_spouse(async_client)
    headers = {"Authorization": f"Bearer {h_token}"}

    cats = (await async_client.get("/api/v1/categories", headers=headers)).json()
    salary = next(c for c in cats if c["name"] == "Salary")
    grocery = next(c for c in cats if c["name"] == "Grocery")

    # January 2026: Income 5000, Expense 2000 -> Net savings 3000 (60.00% rate)
    await async_client.post(
        "/api/v1/income",
        json={"amount": "5000.00", "category_id": salary["id"], "income_date": "2026-01-10", "title": "Jan Salary"},
        headers=headers,
    )
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "2000.00", "category_id": grocery["id"], "expense_date": "2026-01-15", "title": "Jan Groceries"},
        headers=headers,
    )

    # February 2026: Income 6000, Expense 1500 -> Net savings 4500 (75.00% rate)
    await async_client.post(
        "/api/v1/income",
        json={"amount": "6000.00", "category_id": salary["id"], "income_date": "2026-02-10", "title": "Feb Salary"},
        headers=headers,
    )
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "1500.00", "category_id": grocery["id"], "expense_date": "2026-02-18", "title": "Feb Groceries"},
        headers=headers,
    )

    # Fetch Monthly Report
    resp = await async_client.get("/api/v1/reports/monthly?year=2026", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["year"] == 2026
    assert data["total_income"] == "11000.00"
    assert data["total_expenses"] == "3500.00"
    assert data["net_savings"] == "7500.00"
    assert data["overall_savings_rate"] == "68.18"

    months = data["months"]
    assert len(months) == 12

    # Month 1 (January)
    m1 = months[0]
    assert m1["month"] == 1
    assert m1["month_name"] == "January"
    assert m1["income"] == "5000.00"
    assert m1["expenses"] == "2000.00"
    assert m1["net_savings"] == "3000.00"
    assert m1["savings_rate"] == "60.00"

    # Month 2 (February)
    m2 = months[1]
    assert m2["month"] == 2
    assert m2["month_name"] == "February"
    assert m2["income"] == "6000.00"
    assert m2["expenses"] == "1500.00"
    assert m2["net_savings"] == "4500.00"
    assert m2["savings_rate"] == "75.00"

    # Month 3 (March - zero entries)
    m3 = months[2]
    assert m3["income"] == "0.00"
    assert m3["expenses"] == "0.00"
    assert m3["net_savings"] == "0.00"


@pytest.mark.asyncio
async def test_category_report_breakdown(async_client: AsyncClient):
    """Test category spending distribution and percentage calculations."""
    h_token, _, _, _ = await create_family_with_spouse(async_client)
    headers = {"Authorization": f"Bearer {h_token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    grocery = next(c for c in cats if c["name"] == "Grocery")
    fuel = next(c for c in cats if c["name"] == "Fuel")

    # Grocery 300.00 (75%)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "300.00", "category_id": grocery["id"], "expense_date": "2026-10-04", "title": "Supermarket"},
        headers=headers,
    )
    # Fuel 100.00 (25%)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "category_id": fuel["id"], "expense_date": "2026-10-05", "title": "Fuel Tank"},
        headers=headers,
    )

    resp = await async_client.get(
        "/api/v1/reports/categories?month=10&year=2026&type=expense",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_amount"] == "400.00"
    assert len(data["categories"]) == 2

    c0 = data["categories"][0]
    assert c0["category_name"] == "Grocery"
    assert c0["amount"] == "300.00"
    assert c0["percentage"] == "75.00"
    assert c0["transaction_count"] == 1

    c1 = data["categories"][1]
    assert c1["category_name"] == "Fuel"
    assert c1["amount"] == "100.00"
    assert c1["percentage"] == "25.00"
    assert c1["transaction_count"] == 1


@pytest.mark.asyncio
async def test_member_report_husband_vs_wife(async_client: AsyncClient):
    """Test member contribution report ('Husband vs Wife' spending comparison)."""
    h_token, w_token, _, _ = await create_family_with_spouse(async_client)
    h_headers = {"Authorization": f"Bearer {h_token}"}
    w_headers = {"Authorization": f"Bearer {w_token}"}

    cats = (await async_client.get("/api/v1/categories", headers=h_headers)).json()
    salary = next(c for c in cats if c["name"] == "Salary")
    rent = next(c for c in cats if c["name"] == "Rent")
    grocery = next(c for c in cats if c["name"] == "Grocery")

    # Husband pays 800.00 total (500 shared Rent, 300 personal)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "500.00", "category_id": rent["id"], "expense_date": "2026-10-01", "title": "Rent", "is_shared": True},
        headers=h_headers,
    )
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "300.00", "category_id": rent["id"], "expense_date": "2026-10-02", "title": "Personal Gadget", "is_shared": False},
        headers=h_headers,
    )

    # Wife pays 400.00 total (200 shared Grocery, 200 personal)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "200.00", "category_id": grocery["id"], "expense_date": "2026-10-03", "title": "Grocery Shared", "is_shared": True},
        headers=w_headers,
    )
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "200.00", "category_id": grocery["id"], "expense_date": "2026-10-04", "title": "Personal Coffee", "is_shared": False},
        headers=w_headers,
    )

    # Wife earns 3000.00
    await async_client.post(
        "/api/v1/income",
        json={"amount": "3000.00", "category_id": salary["id"], "income_date": "2026-10-01", "title": "Wife Salary"},
        headers=w_headers,
    )

    # Total expenses = 1200.00
    # Husband = 800.00 (66.67%)
    # Wife = 400.00 (33.33%)
    resp = await async_client.get(
        "/api/v1/reports/members?month=10&year=2026",
        headers=h_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_expenses"] == "1200.00"
    assert data["shared_expenses"] == "700.00"
    assert data["personal_expenses"] == "500.00"
    assert data["total_income"] == "3000.00"

    members = data["members"]
    assert len(members) == 2

    husband = next(m for m in members if m["user_name"] == "Husband Alpha")
    assert husband["total_paid"] == "800.00"
    assert husband["percentage_of_total"] == "66.67"
    assert husband["shared_expenses"] == "500.00"
    assert husband["personal_expenses"] == "300.00"

    wife = next(m for m in members if m["user_name"] == "Wife Alpha")
    assert wife["total_paid"] == "400.00"
    assert wife["percentage_of_total"] == "33.33"
    assert wife["shared_expenses"] == "200.00"
    assert wife["personal_expenses"] == "200.00"
    assert wife["income_earned"] == "3000.00"


@pytest.mark.asyncio
async def test_payment_methods_report(async_client: AsyncClient):
    """Test payment method breakdown with PostgreSQL aggregation."""
    h_token, _, _, _ = await create_family_with_spouse(async_client)
    headers = {"Authorization": f"Bearer {h_token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    grocery = cats[0]

    # Credit card 500 (50%)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "500.00", "category_id": grocery["id"], "expense_date": "2026-10-01", "payment_method": "credit_card", "title": "Supermarket CC"},
        headers=headers,
    )
    # Cash 300 (30%)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "300.00", "category_id": grocery["id"], "expense_date": "2026-10-02", "payment_method": "cash", "title": "Bakery Cash"},
        headers=headers,
    )
    # UPI 200 (20%)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "200.00", "category_id": grocery["id"], "expense_date": "2026-10-03", "payment_method": "upi", "title": "Vegetable UPI"},
        headers=headers,
    )

    resp = await async_client.get(
        "/api/v1/reports/payment-methods?month=10&year=2026",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_amount"] == "1000.00"
    methods = {m["payment_method"]: m for m in data["payment_methods"]}

    assert methods["credit_card"]["amount"] == "500.00"
    assert methods["credit_card"]["percentage"] == "50.00"
    assert methods["credit_card"]["transaction_count"] == 1

    assert methods["cash"]["amount"] == "300.00"
    assert methods["cash"]["percentage"] == "30.00"

    assert methods["upi"]["amount"] == "200.00"
    assert methods["upi"]["percentage"] == "20.00"


@pytest.mark.asyncio
async def test_reports_multi_tenant_isolation(async_client: AsyncClient):
    """Test strict multi-tenant isolation in reports and dashboard."""
    token_a, _, _, _ = await create_family_with_spouse(async_client)

    # Register second user in another family
    b_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"full_name": "User B", "email": "user.b.reports@example.com", "password": "Password123!"},
    )
    token_b = b_resp.json()["access_token"]
    await async_client.post(
        "/api/v1/families",
        json={"name": "Family B", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # Family B queries dashboard -> all amounts should be 0.00
    dash_b = (
        await async_client.get(
            "/api/v1/dashboard",
            headers={"Authorization": f"Bearer {token_b}"},
        )
    ).json()

    assert dash_b["total_income"] == "0.00"
    assert dash_b["total_expenses"] == "0.00"
    assert dash_b["remaining_balance"] == "0.00"
    assert len(dash_b["recent_transactions"]) == 0


@pytest.mark.asyncio
async def test_reports_date_range_filtering(async_client: AsyncClient):
    """Test date range boundary filtering (transactions outside range are excluded)."""
    h_token, _, _, _ = await create_family_with_spouse(async_client)
    headers = {"Authorization": f"Bearer {h_token}"}

    cats = (await async_client.get("/api/v1/categories?type=expense", headers=headers)).json()
    grocery = cats[0]

    # Expense on 2026-10-05: 100.00 (Inside filter)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "category_id": grocery["id"], "expense_date": "2026-10-05", "title": "Included"},
        headers=headers,
    )
    # Expense on 2026-10-25: 50.00 (Outside filter)
    await async_client.post(
        "/api/v1/expenses",
        json={"amount": "50.00", "category_id": grocery["id"], "expense_date": "2026-10-25", "title": "Excluded"},
        headers=headers,
    )

    # Query with date range 2026-10-01 to 2026-10-10
    resp = await async_client.get(
        "/api/v1/reports/categories?from_date=2026-10-01&to_date=2026-10-10",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Total should only include 100.00, NOT 150.00
    assert data["total_amount"] == "100.00"
