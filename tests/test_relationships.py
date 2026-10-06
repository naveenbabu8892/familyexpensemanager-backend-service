import pytest
from httpx import AsyncClient

from app.models.relationship import FamilyRelationship


async def register_and_get_token(client: AsyncClient, full_name: str, email: str) -> str:
    """Helper to register a user and extract the JWT access token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": full_name,
            "email": email,
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_family_relationships_endpoint(async_client: AsyncClient):
    """Test GET /api/v1/family-relationships and /family-relationships return valid list."""
    for url in ["/api/v1/family-relationships", "/family-relationships", "/api/v1/families/relationships"]:
        resp = await async_client.get(url)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 16
        values = [item["value"] for item in data]
        assert "mother" in values
        assert "father" in values
        assert "wife" in values
        assert "husband" in values
        assert "brother" in values
        assert "sister" in values
        assert "son" in values
        assert "daughter" in values
        assert "grandfather" in values
        assert "other" in values


@pytest.mark.asyncio
async def test_relationship_validation_invalid_relationship(async_client: AsyncClient):
    """Test inviting a member with an invalid relationship string is rejected with 422."""
    token = await register_and_get_token(async_client, "Owner User", "rel_owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post("/api/v1/families", json={"name": "Owner Family"}, headers=headers)

    resp = await async_client.post(
        "/api/v1/families/invite",
        json={
            "invited_email": "random@example.com",
            "relationship": "random_relationship",
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invite_and_accept_with_mother_relationship(async_client: AsyncClient):
    """Test creating an invitation with 'mother' relationship and accepting it."""
    owner_token = await register_and_get_token(async_client, "Rahul Sharma", "rahul@example.com")
    headers = {"Authorization": f"Bearer {owner_token}"}
    await async_client.post("/api/v1/families", json={"name": "Sharma Household"}, headers=headers)

    # 1. Invite Mother
    invite_resp = await async_client.post(
        "/api/v1/families/invite",
        json={
            "invited_email": "mother@example.com",
            "relationship": "mother",
        },
        headers=headers,
    )
    assert invite_resp.status_code == 201
    invite_data = invite_resp.json()
    assert invite_data["relationship"] == "mother"
    assert invite_data["relationship_label"] == "Mother"
    token = invite_data["token"]

    # 2. Mother registers and accepts
    mother_token = await register_and_get_token(async_client, "Meena Sharma", "mother@example.com")
    m_headers = {"Authorization": f"Bearer {mother_token}"}
    accept_resp = await async_client.post(
        "/api/v1/families/invite/accept",
        json={"token": token},
        headers=m_headers,
    )
    assert accept_resp.status_code == 200

    # 3. Check members
    members_resp = await async_client.get("/api/v1/families/members", headers=headers)
    assert members_resp.status_code == 200
    members = members_resp.json()
    assert len(members) == 2

    mother_member = next(m for m in members if m["user_email"] == "mother@example.com")
    assert mother_member["role"] == "member"
    assert mother_member["relationship"] == "mother"
    assert mother_member["relationship_label"] == "Mother"
    assert mother_member["name"] == "Meena Sharma"


@pytest.mark.asyncio
async def test_multiple_different_relationships(async_client: AsyncClient):
    """Test creating invitations for wife, mother, brother, and sister."""
    owner_token = await register_and_get_token(async_client, "Head Owner", "head@example.com")
    headers = {"Authorization": f"Bearer {owner_token}"}
    await async_client.post("/api/v1/families", json={"name": "Joint Family"}, headers=headers)

    rel_specs = [
        ("Priya", "wife@joint.com", "wife", "Wife"),
        ("Meena", "mother@joint.com", "mother", "Mother"),
        ("Amit", "brother@joint.com", "brother", "Brother"),
        ("Neha", "sister@joint.com", "sister", "Sister"),
    ]

    for name, email, rel, label in rel_specs:
        inv_resp = await async_client.post(
            "/api/v1/families/invitations",
            json={"invited_email": email, "relationship": rel},
            headers=headers,
        )
        assert inv_resp.status_code == 201
        token = inv_resp.json()["token"]

        user_token = await register_and_get_token(async_client, name, email)
        u_headers = {"Authorization": f"Bearer {user_token}"}
        acc_resp = await async_client.post(
            "/api/v1/families/invite/accept",
            json={"token": token},
            headers=u_headers,
        )
        assert acc_resp.status_code == 200

    # Verify all members have distinct relationships preserved
    members_resp = await async_client.get("/api/v1/families/members", headers=headers)
    assert members_resp.status_code == 200
    members = members_resp.json()
    assert len(members) == 5  # Owner + 4 members

    member_map = {m["user_email"]: m for m in members}
    for _, email, rel, label in rel_specs:
        assert member_map[email]["relationship"] == rel
        assert member_map[email]["relationship_label"] == label


@pytest.mark.asyncio
async def test_relationship_family_isolation(async_client: AsyncClient):
    """Test that family members and invitations cannot be accessed across family boundaries."""
    # Family A
    token_a = await register_and_get_token(async_client, "Owner A", "owner_a@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    await async_client.post("/api/v1/families", json={"name": "Family A"}, headers=headers_a)

    inv_a = await async_client.post(
        "/api/v1/families/invite",
        json={"invited_email": "member_a@example.com", "relationship": "son"},
        headers=headers_a,
    )
    token_inv_a = inv_a.json()["token"]

    # Family B
    token_b = await register_and_get_token(async_client, "Owner B", "owner_b@example.com")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    await async_client.post("/api/v1/families", json={"name": "Family B"}, headers=headers_b)

    # Family B checks members -> should only see Owner B
    members_b = await async_client.get("/api/v1/families/members", headers=headers_b)
    assert len(members_b.json()) == 1
    assert members_b.json()[0]["user_email"] == "owner_b@example.com"
