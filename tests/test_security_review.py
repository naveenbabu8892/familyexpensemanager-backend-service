import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
import jwt

from app.core.config import settings
from app.core.security import create_access_token


async def create_authenticated_user_with_family(
    client: AsyncClient,
    email: str,
    name: str = "Test User",
    family_name: str = "Test Family",
) -> tuple[str, str]:
    """Helper to register, login, and create a family for a user."""
    # Register
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": name},
    )
    assert reg_res.status_code == 201

    # Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data["access_token"]

    # Create Family
    fam_res = await client.post(
        "/api/v1/families",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": family_name, "currency": "USD", "timezone": "UTC"},
    )
    assert fam_res.status_code == 201
    family_id = fam_res.json()["id"]

    return token, family_id


# ============================================================================
# 1. MULTI-TENANT ISOLATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_expense(async_client: AsyncClient):
    """Verify that User A cannot read, update, or delete User B's family expense."""
    # User B (Family B)
    token_b, _ = await create_authenticated_user_with_family(
        async_client, "user_b@example.com", "User B", "Family B"
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Fetch default Grocery category for User B
    cat_res = await async_client.get("/api/v1/categories?type=EXPENSE", headers=headers_b)
    cat_b_id = cat_res.json()[0]["id"]

    # Create expense in Family B
    exp_res = await async_client.post(
        "/api/v1/expenses",
        headers=headers_b,
        json={
            "amount": "150.00",
            "category_id": cat_b_id,
            "expense_date": "2026-10-01",
            "payment_method": "credit_card",
            "title": "Family B Secret Grocery",
            "is_shared": True,
        },
    )
    assert exp_res.status_code == 201
    expense_b_id = exp_res.json()["id"]

    # User A (Family A)
    token_a, _ = await create_authenticated_user_with_family(
        async_client, "user_a@example.com", "User A", "Family A"
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User A tries to GET User B's expense -> 404 (Not Found, prevents enumeration)
    get_res = await async_client.get(f"/api/v1/expenses/{expense_b_id}", headers=headers_a)
    assert get_res.status_code == 404
    assert get_res.json()["error"]["message"] == "Expense not found."

    # User A tries to PUT User B's expense -> 404
    put_res = await async_client.put(
        f"/api/v1/expenses/{expense_b_id}",
        headers=headers_a,
        json={"title": "Hacked Title", "amount": "999.00"},
    )
    assert put_res.status_code == 404

    # User A tries to DELETE User B's expense -> 404
    del_res = await async_client.delete(f"/api/v1/expenses/{expense_b_id}", headers=headers_a)
    assert del_res.status_code == 404

    # Confirm expense still exists untouched for User B
    check_res = await async_client.get(f"/api/v1/expenses/{expense_b_id}", headers=headers_b)
    assert check_res.status_code == 200
    assert check_res.json()["title"] == "Family B Secret Grocery"


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_income(async_client: AsyncClient):
    """Verify that User A cannot read, update, or delete User B's family income."""
    # User B (Family B)
    token_b, _ = await create_authenticated_user_with_family(
        async_client, "income_b@example.com", "User B", "Family B"
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Fetch default Salary category
    cat_res = await async_client.get("/api/v1/categories?type=INCOME", headers=headers_b)
    cat_b_id = cat_res.json()[0]["id"]

    # Create income in Family B
    inc_res = await async_client.post(
        "/api/v1/income",
        headers=headers_b,
        json={
            "amount": "5000.00",
            "category_id": cat_b_id,
            "income_date": "2026-10-01",
            "title": "Family B Secret Salary",
        },
    )
    assert inc_res.status_code == 201
    income_b_id = inc_res.json()["id"]

    # User A (Family A)
    token_a, _ = await create_authenticated_user_with_family(
        async_client, "income_a@example.com", "User A", "Family A"
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User A tries to GET User B's income -> 404
    get_res = await async_client.get(f"/api/v1/income/{income_b_id}", headers=headers_a)
    assert get_res.status_code == 404

    # User A tries to PUT User B's income -> 404
    put_res = await async_client.put(
        f"/api/v1/income/{income_b_id}",
        headers=headers_a,
        json={"title": "Hacked Salary"},
    )
    assert put_res.status_code == 404

    # User A tries to DELETE User B's income -> 404
    del_res = await async_client.delete(f"/api/v1/income/{income_b_id}", headers=headers_a)
    assert del_res.status_code == 404

    # Confirm income untouched for User B
    check_res = await async_client.get(f"/api/v1/income/{income_b_id}", headers=headers_b)
    assert check_res.status_code == 200
    assert check_res.json()["title"] == "Family B Secret Salary"


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_budget(async_client: AsyncClient):
    """Verify that User A cannot read, update, or delete User B's family budget."""
    # User B (Family B)
    token_b, _ = await create_authenticated_user_with_family(
        async_client, "budget_b@example.com", "User B", "Family B"
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    cat_res = await async_client.get("/api/v1/categories?type=EXPENSE", headers=headers_b)
    cat_b_id = cat_res.json()[0]["id"]

    # Create budget in Family B
    b_res = await async_client.post(
        "/api/v1/budgets",
        headers=headers_b,
        json={
            "category_id": cat_b_id,
            "amount": "800.00",
            "month": 10,
            "year": 2026,
        },
    )
    assert b_res.status_code == 201
    budget_b_id = b_res.json()["id"]

    # User A (Family A)
    token_a, _ = await create_authenticated_user_with_family(
        async_client, "budget_a@example.com", "User A", "Family A"
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User A tries to GET User B's budget -> 404
    get_res = await async_client.get(f"/api/v1/budgets/{budget_b_id}", headers=headers_a)
    assert get_res.status_code == 404

    # User A tries to PUT User B's budget -> 404
    put_res = await async_client.put(
        f"/api/v1/budgets/{budget_b_id}",
        headers=headers_a,
        json={"amount": "100.00"},
    )
    assert put_res.status_code == 404

    # User A tries to DELETE User B's budget -> 404
    del_res = await async_client.delete(f"/api/v1/budgets/{budget_b_id}", headers=headers_a)
    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_family(async_client: AsyncClient):
    """Verify that User A cannot see or manipulate User B's family data."""
    # User B
    token_b, family_b_id = await create_authenticated_user_with_family(
        async_client, "fam_b@example.com", "User B", "Family Bravo"
    )
    # User A
    token_a, family_a_id = await create_authenticated_user_with_family(
        async_client, "fam_a@example.com", "User A", "Family Alpha"
    )

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User A GET /families/current strictly returns Family Alpha
    fam_res = await async_client.get("/api/v1/families/current", headers=headers_a)
    assert fam_res.status_code == 200
    assert fam_res.json()["id"] == family_a_id
    assert fam_res.json()["name"] == "Family Alpha"
    assert fam_res.json()["id"] != family_b_id


# ============================================================================
# 2. ROLE-BASED ACCESS CONTROL & PRIVILEGE ESCALATION
# ============================================================================

@pytest.mark.asyncio
async def test_family_member_cannot_modify_family_settings_or_invite(async_client: AsyncClient):
    """Verify that a non-owner family member cannot update family settings or send invitations."""
    # Owner creates family
    owner_token, _ = await create_authenticated_user_with_family(
        async_client, "owner@example.com", "Owner User", "Shared Family"
    )
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Invite Member
    invite_res = await async_client.post(
        "/api/v1/families/invite",
        headers=owner_headers,
        json={"invited_email": "member@example.com"},
    )
    assert invite_res.status_code == 201
    invite_token = invite_res.json()["token"]

    # Member registers and logs in
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "member@example.com", "password": "SecurePassword123!", "full_name": "Spouse Member"},
    )
    m_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": "SecurePassword123!"},
    )
    member_token = m_login.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Accept invitation
    acc_res = await async_client.post(
        "/api/v1/families/invite/accept",
        headers=member_headers,
        json={"token": invite_token},
    )
    assert acc_res.status_code == 200

    # Member attempts to update family settings -> 403 Forbidden
    put_res = await async_client.put(
        "/api/v1/families/current",
        headers=member_headers,
        json={"name": "Hacked Family Name"},
    )
    assert put_res.status_code == 403
    assert "Only the family owner has permission to update family settings" in put_res.json()["error"]["message"]

    # Member attempts to send an invitation -> 403 Forbidden
    inv_res = await async_client.post(
        "/api/v1/families/invite",
        headers=member_headers,
        json={"invited_email": "intruder@example.com"},
    )
    assert inv_res.status_code == 403
    assert "Only the family owner can invite new members" in inv_res.json()["error"]["message"]


# ============================================================================
# 3. JWT AUTHENTICATION & TOKEN SECURITY
# ============================================================================

@pytest.mark.asyncio
async def test_invalid_jwt_rejected(async_client: AsyncClient):
    """Verify that forged, malformed, or tampered JWTs return 401 Unauthorized."""
    # Malformed token
    res1 = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert res1.status_code == 401
    assert res1.json()["error"]["message"] == "Could not validate credentials."

    # Valid structure but forged signature (wrong secret)
    forged_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "hacker@example.com",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        "completely-wrong-secret-key-1234567890",
        algorithm="HS256",
    )
    res2 = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert res2.status_code == 401
    assert res2.json()["error"]["message"] == "Could not validate credentials."


@pytest.mark.asyncio
async def test_expired_jwt_rejected(async_client: AsyncClient):
    """Verify that an expired JWT returns 401 with explicit expiration error message."""
    expired_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "email": "expired@example.com"},
        expires_delta=timedelta(seconds=-10),  # expired 10s ago
    )
    res = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["message"] == "Token has expired."


@pytest.mark.asyncio
async def test_revoked_refresh_token_rejected(async_client: AsyncClient):
    """Verify that logging out revokes the refresh token and prevents further refreshing."""
    # Register and login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "logout_test@example.com", "password": "SecurePassword123!", "full_name": "Logout Tester"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "logout_test@example.com", "password": "SecurePassword123!"},
    )
    tokens = login_res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200

    # Attempt to refresh with the revoked token -> 401
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 401
    assert refresh_res.json()["error"]["message"] == "Invalid or revoked refresh token."


# ============================================================================
# 4. INVITATION LIFECYCLE & SECURITY
# ============================================================================

@pytest.mark.asyncio
async def test_invalid_invitation_cannot_be_accepted(async_client: AsyncClient):
    """Verify that a non-existent or invalid invitation token is rejected."""
    token, _ = await create_authenticated_user_with_family(
        async_client, "invite_inv@example.com", "Invite Tester", "Test Family"
    )
    # Register another user to attempt acceptance
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "invitee@example.com", "password": "SecurePassword123!", "full_name": "Invitee"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "invitee@example.com", "password": "SecurePassword123!"},
    )
    invitee_token = login_res.json()["access_token"]

    # Attempt to accept fabricated token -> 404
    acc_res = await async_client.post(
        "/api/v1/families/invite/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": "completely-invalid-invitation-token-12345"},
    )
    assert acc_res.status_code == 404
    assert "Invalid invitation token" in acc_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_expired_invitation_cannot_be_accepted(async_client: AsyncClient):
    """Verify that an expired invitation token returns 400."""
    from app.core.database import AsyncSessionLocal
    from app.models.family import FamilyInvitation
    from sqlalchemy import select

    owner_token, _ = await create_authenticated_user_with_family(
        async_client, "owner_exp@example.com", "Owner Exp", "Family Exp"
    )
    # Create invitation
    inv_res = await async_client.post(
        "/api/v1/families/invite",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"invited_email": "expired_invitee@example.com"},
    )
    assert inv_res.status_code == 201
    invite_token = inv_res.json()["token"]

    # Manually expire the invitation in DB
    async with AsyncSessionLocal() as session:
        stmt = select(FamilyInvitation).where(FamilyInvitation.token == invite_token)
        result = await session.execute(stmt)
        invitation = result.scalar_one()
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await session.commit()

    # Invitee registers & attempts acceptance
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "expired_invitee@example.com", "password": "SecurePassword123!", "full_name": "Invitee Exp"},
    )
    l_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "expired_invitee@example.com", "password": "SecurePassword123!"},
    )
    invitee_token = l_res.json()["access_token"]

    acc_res = await async_client.post(
        "/api/v1/families/invite/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": invite_token},
    )
    assert acc_res.status_code == 400
    assert "expired" in acc_res.json()["error"]["message"].lower()


# ============================================================================
# 5. SQL INJECTION PROTECTION
# ============================================================================

@pytest.mark.asyncio
async def test_sql_injection_payloads_safely_handled(async_client: AsyncClient):
    """Verify that SQL injection payloads in queries, filters, and body fields are safely neutralized."""
    token, _ = await create_authenticated_user_with_family(
        async_client, "sqli_test@example.com", "SQLi Tester", "Family SQLi"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch valid category
    cat_res = await async_client.get("/api/v1/categories?type=EXPENSE", headers=headers)
    valid_cat_id = cat_res.json()[0]["id"]

    # 1. SQL Injection payload in text field
    sqli_title = "Dinner'; DROP TABLE expenses; SELECT * FROM users WHERE '1'='1"
    exp_res = await async_client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": "45.00",
            "category_id": valid_cat_id,
            "expense_date": "2026-10-01",
            "payment_method": "cash",
            "title": sqli_title,
            "is_shared": False,
        },
    )
    assert exp_res.status_code == 201
    # The title is stored as plain text, not executed as SQL
    assert exp_res.json()["title"] == sqli_title

    # 2. SQL Injection payload in query search parameter
    search_res = await async_client.get(
        "/api/v1/expenses?search=' OR '1'='1' --",
        headers=headers,
    )
    assert search_res.status_code == 200
    # No SQL syntax crash; returns safely filtered data
    data = search_res.json()
    assert "items" in data

    # 3. SQL Injection in category filter (should validate as UUID)
    bad_cat_res = await async_client.get(
        "/api/v1/expenses?category_id=1' OR '1'='1",
        headers=headers,
    )
    assert bad_cat_res.status_code == 422  # Pydantic UUID validation halts it before DB


# ============================================================================
# 6. INPUT VALIDATION & NUMERIC PRECISION
# ============================================================================

@pytest.mark.asyncio
async def test_input_validation_negative_amounts_and_zero_budget(async_client: AsyncClient):
    """Verify that negative amounts and invalid inputs are rejected with 422."""
    token, _ = await create_authenticated_user_with_family(
        async_client, "validation@example.com", "Val Tester", "Val Family"
    )
    headers = {"Authorization": f"Bearer {token}"}
    cat_res = await async_client.get("/api/v1/categories?type=EXPENSE", headers=headers)
    cat_id = cat_res.json()[0]["id"]

    # Negative expense amount -> 422
    neg_exp = await async_client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": "-50.00",
            "category_id": cat_id,
            "expense_date": "2026-10-01",
            "payment_method": "cash",
            "title": "Negative Test",
            "is_shared": False,
        },
    )
    assert neg_exp.status_code == 422

    # Zero budget amount -> 422
    zero_bgt = await async_client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": "0.00",
            "month": 10,
            "year": 2026,
        },
    )
    assert zero_bgt.status_code == 422

    # Invalid month (e.g. 13) -> 422
    inv_month = await async_client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": "500.00",
            "month": 13,
            "year": 2026,
        },
    )
    assert inv_month.status_code == 422


# ============================================================================
# 7. RATE LIMITING STRATEGY
# ============================================================================

@pytest.mark.asyncio
async def test_auth_rate_limiting_enforced(async_client: AsyncClient):
    """Verify that exceeding the auth rate limit triggers HTTP 429 Too Many Requests."""
    # Ensure fresh rate limiter bucket for test client
    from app.core.rate_limit import limiter
    limiter.history.clear()

    triggered = False
    for i in range(25):
        res = await async_client.post(
            "/api/v1/auth/login",
            headers={"X-Test-Rate-Limit": "1"},
            json={"email": "nonexistent@example.com", "password": "WrongPassword123!"},
        )
        if res.status_code == 429:
            triggered = True
            assert res.json()["error"]["message"] == "Too many requests. Please try again later."
            assert "retry-after" in res.headers
            break

    assert triggered is True, "Expected 429 Too Many Requests to be triggered on repeated login attempts"


# ============================================================================
# 8. PASSWORD & TOKEN SECURITY STORAGE
# ============================================================================

@pytest.mark.asyncio
async def test_password_and_token_storage_security(async_client: AsyncClient):
    """Verify that passwords use Argon2id and refresh tokens are hashed in DB."""
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.models.token import RefreshToken
    from sqlalchemy import select

    email = "security_verify@example.com"
    pwd = "MySecretPassword123!"

    # Register
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "full_name": "Security User"},
    )
    assert reg_res.status_code == 201

    # Login to generate refresh token
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pwd},
    )
    raw_refresh_token = login_res.json()["refresh_token"]

    async with AsyncSessionLocal() as session:
        # Check user password
        u_res = await session.execute(select(User).where(User.email == email))
        db_user = u_res.scalar_one()

        # 1. Plain text password must NEVER be in database
        assert db_user.password_hash != pwd
        # 2. Must be Argon2id hashed
        assert db_user.password_hash.startswith("$argon2id$")

        # 3. Refresh token must NOT be stored in raw format
        rt_res = await session.execute(
            select(RefreshToken).where(RefreshToken.user_id == db_user.id)
        )
        db_tokens = rt_res.scalars().all()
        assert len(db_tokens) > 0
        # Check all stored refresh tokens
        for db_token in db_tokens:
            assert db_token.token_hash != raw_refresh_token
            assert len(db_token.token_hash) == 64  # SHA-256 hex digest length
