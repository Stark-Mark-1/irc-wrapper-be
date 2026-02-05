from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ambio_ai_chat import AmbioAiChat


async def get_or_create_chat(
    *,
    db: AsyncSession,
    session_id: str,
    chat_id: str | None,
    prompt: str,
) -> AmbioAiChat:
    if chat_id:
        existing = await db.scalar(select(AmbioAiChat).where(AmbioAiChat.chat_id == chat_id))
        if existing:
            return existing

    chat = AmbioAiChat(
        chat_id=str(uuid.uuid4()),
        session_id=session_id,
        title=(prompt or "")[:50],
        is_archived=False,
        created_at=datetime.utcnow(),
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


async def list_chats_for_session(db: AsyncSession, session_id: str) -> list[AmbioAiChat]:
    res = await db.execute(
        select(AmbioAiChat)
        .where(AmbioAiChat.session_id == session_id, AmbioAiChat.is_archived.is_(False))
        .order_by(AmbioAiChat.created_at.desc())
    )
    return list(res.scalars().all())

