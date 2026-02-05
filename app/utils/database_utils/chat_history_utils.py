from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ambio_ai_chat_history import AmbioAiChatHistory
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
) -> AmbioAiChatHistory:
    msg = AmbioAiChatHistory(
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


async def get_chat_history_by_chat_id(db: AsyncSession, chat_id: str) -> list[AmbioAiChatHistory]:
    res = await db.execute(
        select(AmbioAiChatHistory).where(AmbioAiChatHistory.chat_id == chat_id).order_by(AmbioAiChatHistory.created_at.asc())
    )
    return list(res.scalars().all())


async def count_user_messages_for_session_by_mode(db: AsyncSession, session_id: str, mode: str) -> int:
    # Count across all chats belonging to session_id
    from app.models.ambio_ai_chat import AmbioAiChat

    stmt = (
        select(func.count(AmbioAiChatHistory.chat_history_id))
        .select_from(AmbioAiChatHistory)
        .join(AmbioAiChat, AmbioAiChat.chat_id == AmbioAiChatHistory.chat_id)
        .where(
            AmbioAiChat.session_id == session_id,
            AmbioAiChatHistory.role == ChatRole.USER,
            AmbioAiChatHistory.mode == mode,
        )
    )
    val = await db.scalar(stmt)
    return int(val or 0)

