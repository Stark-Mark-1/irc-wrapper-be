from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_anonymous_session(async_client: AsyncClient) -> None:
    """Test creating an anonymous session."""
    response = await async_client.post("/api/v1/session")
    assert response.status_code == 200

    data = response.json()
    assert "session_id" in data
    assert data["user_type"] == "anonymous"
    assert data["reference_type"] == "NON_SIGNED_IN_USER"


@pytest.mark.asyncio
async def test_create_authenticated_session_with_user_id(async_client: AsyncClient) -> None:
    """Test creating an authenticated session with x-user-id header."""
    response = await async_client.post(
        "/api/v1/session",
        headers={"x-user-id": "test-user-123"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "session_id" in data
    assert data["user_type"] == "authenticated"
    assert data["reference_type"] == "SIGNED_IN_USER"


@pytest.mark.asyncio
async def test_session_reuse(async_client: AsyncClient) -> None:
    """Test that same user gets same session."""
    # Create first session
    response1 = await async_client.post(
        "/api/v1/session",
        headers={"x-user-id": "reuse-user"},
    )
    session_id_1 = response1.json()["session_id"]

    # Create second session with same user
    response2 = await async_client.post(
        "/api/v1/session",
        headers={"x-user-id": "reuse-user"},
    )
    session_id_2 = response2.json()["session_id"]

    assert session_id_1 == session_id_2


@pytest.mark.asyncio
async def test_delete_session(async_client: AsyncClient) -> None:
    """Test deleting/invalidating a session."""
    # Create session
    response = await async_client.post("/api/v1/session")
    session_id = response.json()["session_id"]

    # Delete session
    response = await async_client.delete(
        "/api/v1/session",
        headers={"x-session-id": session_id},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Session invalidated successfully."


@pytest.mark.asyncio
async def test_delete_session_missing_header(async_client: AsyncClient) -> None:
    """Test delete session without header."""
    response = await async_client.delete("/api/v1/session")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_session_invalid_session(async_client: AsyncClient) -> None:
    """Test delete session with invalid session."""
    response = await async_client.delete(
        "/api/v1/session",
        headers={"x-session-id": "invalid-session-id"},
    )
    assert response.status_code == 401
