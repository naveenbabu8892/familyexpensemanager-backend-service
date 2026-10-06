import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Test root endpoint returns API information."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """Test /health endpoint format."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "app_name" in data
    assert "version" in data
    assert "environment" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_health_check_database_connected(async_client: AsyncClient):
    """Test health check reports healthy when DB is connected."""
    with patch("app.routers.health.check_database_connection", return_value=(True, "connected")):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_check_database_disconnected(async_client: AsyncClient):
    """Test health check reports degraded when DB is unreachable."""
    with patch("app.routers.health.check_database_connection", return_value=(False, "Connection refused")):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert "disconnected" in data["database"]


@pytest.mark.asyncio
async def test_liveness_endpoint(async_client: AsyncClient):
    """Test liveness probe endpoint."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_v1_health_prefix(async_client: AsyncClient):
    """Test that health is also available under /api/v1 prefix."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_not_found_exception_handling(async_client: AsyncClient):
    """Test global error handler format for 404 Not Found."""
    response = await async_client.get("/non-existent-path")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == 404
