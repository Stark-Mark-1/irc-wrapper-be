from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.database import get_db
from app.models.ambio_ai_prompts import AmbioAiPrompts
from app.utils.audit_logger import log_admin_action

router = APIRouter()
logger = logging.getLogger(__name__)


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)


class PromptResponse(BaseModel):
    prompt_id: str
    name: str
    content: str
    is_archived: bool


def validate_admin_token(token: str | None) -> None:
    """Validate that the provided token matches the admin API token."""
    if not token or token != settings.admin_api_token:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token.")


@router.put("/prompts")
async def create_or_update_prompt(
    request: Request,
    body: PromptCreate,
    x_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create or update a prompt template. Requires admin token."""
    validate_admin_token(x_token)

    # Check if prompt with this name exists
    existing = await db.scalar(
        select(AmbioAiPrompts).where(AmbioAiPrompts.name == body.name)
    )

    if existing:
        # Update existing prompt
        existing.content = body.content
        existing.is_archived = False  # Unarchive if it was archived
        await db.commit()
        await db.refresh(existing)
        logger.info(f"Prompt updated: {body.name}")
        log_admin_action("prompt_updated", request, {"prompt_name": body.name, "prompt_id": existing.prompt_id})
        return {"prompt_id": existing.prompt_id, "name": existing.name, "action": "updated"}

    # Create new prompt
    prompt = AmbioAiPrompts(name=body.name, content=body.content)
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    logger.info(f"Prompt created: {body.name}")
    log_admin_action("prompt_created", request, {"prompt_name": body.name, "prompt_id": prompt.prompt_id})
    return {"prompt_id": prompt.prompt_id, "name": prompt.name, "action": "created"}


@router.get("/prompts")
async def list_prompts(db: AsyncSession = Depends(get_db)) -> list[PromptResponse]:
    """Get all non-archived prompts."""
    result = await db.execute(
        select(AmbioAiPrompts).where(AmbioAiPrompts.is_archived.is_(False))
    )
    prompts = list(result.scalars().all())
    return [
        PromptResponse(
            prompt_id=p.prompt_id,
            name=p.name,
            content=p.content,
            is_archived=p.is_archived,
        )
        for p in prompts
    ]
