from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rehab_ai_chat import RehabAiChat


async def get_or_create_chat(
    *,
    db: AsyncSession,
    session_id: str,
    chat_id: str | None,
    prompt: str,
) -> RehabAiChat:
    if chat_id:
        existing = await db.scalar(select(RehabAiChat).where(RehabAiChat.chat_id == chat_id))
        if existing:
            return existing

    chat = RehabAiChat(
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


async def list_chats_for_session(db: AsyncSession, session_id: str) -> list[RehabAiChat]:
    res = await db.execute(
        select(RehabAiChat)
        .where(RehabAiChat.session_id == session_id, RehabAiChat.is_archived.is_(False))
        .order_by(RehabAiChat.created_at.desc())
    )
    return list(res.scalars().all())

