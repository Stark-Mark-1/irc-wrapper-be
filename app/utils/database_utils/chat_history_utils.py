from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rehab_ai_chat_history import RehabAiChatHistory
from app.models.enums import ChatRole


async def create_chat_message(
    *,
    db: AsyncSession,
    chat_id: str,
    role: ChatRole,
    mode: str,
    content: str,
    meta: dict[str, Any] | None = None,
    previous_message_id: str | None = None,
) -> RehabAiChatHistory:
    msg = RehabAiChatHistory(
        chat_history_id=str(uuid.uuid4()),
        chat_id=chat_id,
        previous_message_id=previous_message_id,
        role=role,
        mode=mode,
        content=content,
        meta=meta,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_chat_history_by_chat_id(db: AsyncSession, chat_id: str) -> list[RehabAiChatHistory]:
    res = await db.execute(
        select(RehabAiChatHistory).where(RehabAiChatHistory.chat_id == chat_id).order_by(RehabAiChatHistory.created_at.asc())
    )
    return list(res.scalars().all())


async def count_user_messages_for_session_by_mode(db: AsyncSession, session_id: str, mode: str) -> int:
    # Count across all chats belonging to session_id
    from app.models.rehab_ai_chat import RehabAiChat

    stmt = (
        select(func.count(RehabAiChatHistory.chat_history_id))
        .select_from(RehabAiChatHistory)
        .join(RehabAiChat, RehabAiChat.chat_id == RehabAiChatHistory.chat_id)
        .where(
            RehabAiChat.session_id == session_id,
            RehabAiChatHistory.role == ChatRole.USER,
            RehabAiChatHistory.mode == mode,
        )
    )
    val = await db.scalar(stmt)
    return int(val or 0)

