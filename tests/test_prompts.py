from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_prompt_requires_admin_token(async_client: AsyncClient) -> None:
    """Test that creating a prompt requires admin token."""
    response = await async_client.put(
        "/api/v1/prompts",
        json={"name": "test-prompt", "content": "Test content"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_prompt_invalid_token(async_client: AsyncClient) -> None:
    """Test that invalid admin token is rejected."""
    response = await async_client.put(
        "/api/v1/prompts",
        json={"name": "test-prompt", "content": "Test content"},
        headers={"x-token": "invalid-token"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_prompt_success(async_client: AsyncClient) -> None:
    """Test creating a prompt with valid admin token."""
    response = await async_client.put(
        "/api/v1/prompts",
        json={"name": "test-prompt", "content": "Test content"},
        headers={"x-token": "test-admin-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-prompt"
    assert data["action"] == "created"


@pytest.mark.asyncio
async def test_update_prompt(async_client: AsyncClient) -> None:
    """Test updating an existing prompt."""
    # Create prompt
    await async_client.put(
        "/api/v1/prompts",
        json={"name": "update-test", "content": "Original content"},
        headers={"x-token": "test-admin-token"},
    )

    # Update prompt
    response = await async_client.put(
        "/api/v1/prompts",
        json={"name": "update-test", "content": "Updated content"},
        headers={"x-token": "test-admin-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "update-test"
    assert data["action"] == "updated"


@pytest.mark.asyncio
async def test_list_prompts_empty(async_client: AsyncClient) -> None:
    """Test listing prompts when none exist."""
    response = await async_client.get("/api/v1/prompts")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_prompts(async_client: AsyncClient) -> None:
    """Test listing prompts after creating some."""
    # Create prompts
    await async_client.put(
        "/api/v1/prompts",
        json={"name": "prompt-1", "content": "Content 1"},
        headers={"x-token": "test-admin-token"},
    )
    await async_client.put(
        "/api/v1/prompts",
        json={"name": "prompt-2", "content": "Content 2"},
        headers={"x-token": "test-admin-token"},
    )

    # List prompts
    response = await async_client.get("/api/v1/prompts")
    assert response.status_code == 200
    prompts = response.json()
    assert len(prompts) == 2
    names = [p["name"] for p in prompts]
    assert "prompt-1" in names
    assert "prompt-2" in names
