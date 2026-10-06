import pytest
from httpx import AsyncClient


async def register_and_get_token(client: AsyncClient, name: str, email: str) -> str:
    """Helper to register a user and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "Password123!"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_family(async_client: AsyncClient):
    """Test authenticated user creates a family and becomes the OWNER."""
    token = await register_and_get_token(async_client, "John Doe", "john.doe@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "The Doe Family",
        "currency": "USD",
        "timezone": "America/New_York",
    }
    response = await async_client.post("/api/v1/families", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "The Doe Family"
    assert data["currency"] == "USD"
    assert data["timezone"] == "America/New_York"
    assert data["user_role"] == "owner"


@pytest.mark.asyncio
async def test_user_can_create_only_one_family(async_client: AsyncClient):
    """Test user cannot create more than one family."""
    token = await register_and_get_token(async_client, "Single Family User", "single@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create first family
    resp1 = await async_client.post(
        "/api/v1/families",
        json={"name": "Family One"},
        headers=headers,
    )
    assert resp1.status_code == 201

    # Attempt to create second family
    resp2 = await async_client.post(
        "/api/v1/families",
        json={"name": "Family Two"},
        headers=headers,
    )
    assert resp2.status_code == 400
    assert "already belongs to an active family" in resp2.json()["error"]["message"]


@pytest.mark.asyncio
async def test_get_current_family_when_none(async_client: AsyncClient):
    """Test GET /api/v1/families/current returns 404 if user has no family."""
    token = await register_and_get_token(async_client, "Homeless User", "homeless@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get("/api/v1/families/current", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_current_family_as_owner(async_client: AsyncClient):
    """Test owner updates family name and currency."""
    token = await register_and_get_token(async_client, "Owner User", "owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    await async_client.post("/api/v1/families", json={"name": "Old Name"}, headers=headers)

    update_payload = {"name": "New Family Name", "currency": "EUR"}
    update_resp = await async_client.put(
        "/api/v1/families/current", json=update_payload, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "New Family Name"
    assert update_resp.json()["currency"] == "EUR"


@pytest.mark.asyncio
async def test_spouse_invitation_and_acceptance_flow(async_client: AsyncClient):
    """Test complete flow: Husband invites Wife, Wife accepts and becomes MEMBER."""
    # 1. Husband registers and creates family
    husband_token = await register_and_get_token(
        async_client, "Husband Smith", "husband@example.com"
    )
    h_headers = {"Authorization": f"Bearer {husband_token}"}

    fam_resp = await async_client.post(
        "/api/v1/families", json={"name": "Smith Family"}, headers=h_headers
    )
    assert fam_resp.status_code == 201
    family_id = fam_resp.json()["id"]

    # 2. Husband invites Wife
    invite_resp = await async_client.post(
        "/api/v1/families/invite",
        json={"invited_email": "wife@example.com"},
        headers=h_headers,
    )
    assert invite_resp.status_code == 201
    invitation_data = invite_resp.json()
    assert invitation_data["status"] == "pending"
    assert invitation_data["invited_email"] == "wife@example.com"
    token = invitation_data["token"]

    # 3. Wife registers as user
    wife_token = await register_and_get_token(
        async_client, "Wife Smith", "wife@example.com"
    )
    w_headers = {"Authorization": f"Bearer {wife_token}"}

    # 4. Wife accepts invitation
    accept_resp = await async_client.post(
        "/api/v1/families/invite/accept",
        json={"token": token},
        headers=w_headers,
    )
    assert accept_resp.status_code == 200
    wife_fam = accept_resp.json()
    assert wife_fam["id"] == family_id
    assert wife_fam["user_role"] == "member"

    # 5. Wife checks current family
    w_curr_resp = await async_client.get("/api/v1/families/current", headers=w_headers)
    assert w_curr_resp.status_code == 200
    assert w_curr_resp.json()["id"] == family_id

    # 6. List members (shows both Husband as owner and Wife as member)
    members_resp = await async_client.get("/api/v1/families/members", headers=w_headers)
    assert members_resp.status_code == 200
    members = members_resp.json()
    assert len(members) == 2

    roles = {m["user_email"]: m["role"] for m in members}
    assert roles["husband@example.com"] == "owner"
    assert roles["wife@example.com"] == "member"


@pytest.mark.asyncio
async def test_cannot_accept_invitation_twice(async_client: AsyncClient):
    """Test invitation cannot be accepted more than once."""
    husband_token = await register_and_get_token(async_client, "Husband", "h2@example.com")
    h_headers = {"Authorization": f"Bearer {husband_token}"}
    await async_client.post("/api/v1/families", json={"name": "Family Two"}, headers=h_headers)

    invite_resp = await async_client.post(
        "/api/v1/families/invite",
        json={"invited_email": "w2@example.com"},
        headers=h_headers,
    )
    token = invite_resp.json()["token"]

    wife_token = await register_and_get_token(async_client, "Wife", "w2@example.com")
    w_headers = {"Authorization": f"Bearer {wife_token}"}

    # Accept 1st time
    accept1 = await async_client.post(
        "/api/v1/families/invite/accept", json={"token": token}, headers=w_headers
    )
    assert accept1.status_code == 200

    # Accept 2nd time
    accept2 = await async_client.post(
        "/api/v1/families/invite/accept", json={"token": token}, headers=w_headers
    )
    assert accept2.status_code == 400


@pytest.mark.asyncio
async def test_wrong_user_cannot_accept_invitation(async_client: AsyncClient):
    """Test that a different user cannot accept an invitation meant for someone else."""
    h_token = await register_and_get_token(async_client, "User 1", "u1@example.com")
    h_headers = {"Authorization": f"Bearer {h_token}"}
    await async_client.post("/api/v1/families", json={"name": "U1 Fam"}, headers=h_headers)

    invite_resp = await async_client.post(
        "/api/v1/families/invite",
        json={"invited_email": "intended@example.com"},
        headers=h_headers,
    )
    token = invite_resp.json()["token"]

    # Intruder user logs in
    intruder_token = await register_and_get_token(async_client, "Intruder", "intruder@example.com")
    int_headers = {"Authorization": f"Bearer {intruder_token}"}

    # Attempts to accept invitation
    response = await async_client.post(
        "/api/v1/families/invite/accept", json={"token": token}, headers=int_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_update_family(async_client: AsyncClient):
    """Test non-owner member cannot update family configuration."""
    # Setup family and member
    h_token = await register_and_get_token(async_client, "Husband", "h3@example.com")
    h_headers = {"Authorization": f"Bearer {h_token}"}
    await async_client.post("/api/v1/families", json={"name": "Fam 3"}, headers=h_headers)

    inv = await async_client.post(
        "/api/v1/families/invite", json={"invited_email": "w3@example.com"}, headers=h_headers
    )
    token = inv.json()["token"]

    w_token = await register_and_get_token(async_client, "Wife", "w3@example.com")
    w_headers = {"Authorization": f"Bearer {w_token}"}
    await async_client.post(
        "/api/v1/families/invite/accept", json={"token": token}, headers=w_headers
    )

    # Wife tries to update family
    update_resp = await async_client.put(
        "/api/v1/families/current", json={"name": "Hacked Name"}, headers=w_headers
    )
    assert update_resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_invite_yourself(async_client: AsyncClient):
    """Test owner cannot invite their own email."""
    token = await register_and_get_token(async_client, "Self Inviter", "self@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post("/api/v1/families", json={"name": "Self Fam"}, headers=headers)

    response = await async_client.post(
        "/api/v1/families/invite", json={"invited_email": "self@example.com"}, headers=headers
    )
    assert response.status_code == 400
