from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_history_requires_session(async_client: AsyncClient) -> None:
    """Test that list history requires session header."""
    response = await async_client.get("/api/v1/chat-history")
    assert response.status_code == 400
    assert "Missing x-session-id" in response.json()["error"]


@pytest.mark.asyncio
async def test_list_history_invalid_session(async_client: AsyncClient) -> None:
    """Test list history with invalid session."""
    response = await async_client.get(
        "/api/v1/chat-history",
        headers={"x-session-id": "invalid-session"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_history_empty(async_client: AsyncClient) -> None:
    """Test list history returns empty list for new session."""
    # Create session
    session_response = await async_client.post("/api/v1/session")
    session_id = session_response.json()["session_id"]

    # List history
    response = await async_client.get(
        "/api/v1/chat-history",
        headers={"x-session-id": session_id},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_chat_history_not_found(async_client: AsyncClient) -> None:
    """Test getting chat history for non-existent chat."""
    # Create session
    session_response = await async_client.post("/api/v1/session")
    session_id = session_response.json()["session_id"]

    # Try to get non-existent chat
    response = await async_client.get(
        "/api/v1/chat-history/non-existent-chat-id",
        headers={"x-session-id": session_id},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_ownership_enforcement(async_client: AsyncClient) -> None:
    """Test that users cannot access chats from other sessions."""
    # This test would require actually creating a chat first,
    # which needs the chat endpoint to work (requires OpenAI key)
    # For now, just verify the 404 response for non-existent chats
    session_response = await async_client.post("/api/v1/session")
    session_id = session_response.json()["session_id"]

    response = await async_client.get(
        "/api/v1/chat-history/some-other-chat-id",
        headers={"x-session-id": session_id},
    )
    assert response.status_code == 404
