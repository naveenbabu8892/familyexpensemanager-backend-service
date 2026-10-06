import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    """Test successful user registration returns access and refresh tokens."""
    payload = {
        "full_name": "Alice Wonderland",
        "email": "alice@example.com",
        "password": "StrongPassword123!",
        "phone": "+1234567890",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    """Test duplicate registration returns 409 Conflict."""
    payload = {
        "full_name": "Alice Duplicate",
        "email": "alice@example.com",
        "password": "AnotherPassword123!",
    }
    # Register initially
    resp1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Attempt to register second user with duplicate email
    resp2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["success"] is False
    assert data["error"]["code"] == 409


@pytest.mark.asyncio
async def test_register_invalid_email(async_client: AsyncClient):
    """Test registration with invalid email returns 422 Validation Error."""
    payload = {
        "full_name": "Bad Email",
        "email": "not-an-email",
        "password": "Password123!",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(async_client: AsyncClient):
    """Test registration with password shorter than 8 chars returns 422."""
    payload = {
        "full_name": "Short Pass",
        "email": "short@example.com",
        "password": "short",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    """Test user login returns valid tokens."""
    # Register first
    reg_payload = {
        "full_name": "Bob Builder",
        "email": "bob@example.com",
        "password": "BobSecurePassword123!",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201

    # Login
    login_payload = {
        "email": "bob@example.com",
        "password": "BobSecurePassword123!",
    }
    login_resp = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    """Test login with wrong password returns 401 Unauthorized."""
    login_payload = {
        "email": "bob@example.com",
        "password": "WrongPassword!",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(async_client: AsyncClient):
    """Test login with non-existent user returns 401 Unauthorized."""
    login_payload = {
        "email": "nonexistent@example.com",
        "password": "SomePassword123!",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(async_client: AsyncClient):
    """Test refresh token rotation: old token is invalidated upon use."""
    # Register user
    reg_payload = {
        "full_name": "Charlie Chaplin",
        "email": "charlie@example.com",
        "password": "CharliePassword123!",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    initial_refresh_token = reg_resp.json()["refresh_token"]

    # Refresh
    refresh_payload = {"refresh_token": initial_refresh_token}
    refresh_resp = await async_client.post("/api/v1/auth/refresh", json=refresh_payload)
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    new_access_token = data["access_token"]
    new_refresh_token = data["refresh_token"]

    assert new_access_token is not None
    assert new_refresh_token != initial_refresh_token

    # Attempt to reuse initial refresh token -> should be rejected (revoked by rotation)
    reuse_resp = await async_client.post("/api/v1/auth/refresh", json=refresh_payload)
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_revocation(async_client: AsyncClient):
    """Test logout revokes the refresh token."""
    reg_payload = {
        "full_name": "David Bowie",
        "email": "david@example.com",
        "password": "DavidPassword123!",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=reg_payload)
    refresh_token = reg_resp.json()["refresh_token"]

    # Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Successfully logged out."

    # Try to refresh with the revoked token -> should fail
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_me(async_client: AsyncClient):
    """Test GET /api/v1/users/me with valid Bearer token."""
    reg_payload = {
        "full_name": "Eva Green",
        "email": "eva@example.com",
        "password": "EvaPassword123!",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=reg_payload)
    access_token = reg_resp.json()["access_token"]

    response = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "eva@example.com"
    assert data["full_name"] == "Eva Green"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_get_current_user_me_unauthorized(async_client: AsyncClient):
    """Test GET /api/v1/users/me without token returns 401."""
    response = await async_client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_current_user_me(async_client: AsyncClient):
    """Test PUT /api/v1/users/me updates profile fields."""
    reg_payload = {
        "full_name": "Frank Ocean",
        "email": "frank@example.com",
        "password": "FrankPassword123!",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=reg_payload)
    access_token = reg_resp.json()["access_token"]

    update_payload = {
        "full_name": "Frank Christopher Ocean",
        "phone": "+9876543210",
        "avatar_url": "https://example.com/avatar.jpg",
    }
    update_resp = await async_client.put(
        "/api/v1/users/me",
        json=update_payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["full_name"] == "Frank Christopher Ocean"
    assert data["phone"] == "+9876543210"
    assert data["avatar_url"] == "https://example.com/avatar.jpg"
