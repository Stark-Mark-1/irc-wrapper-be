from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.ambio_ai_chat_history import AmbioAiChatHistory
from app.utils.database_utils.chat_utils import list_chats_for_session
from app.utils.database_utils.session_utils import get_active_session

router = APIRouter()


@router.get("/chat-history")
async def list_history(x_session_id: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing x-session-id header.")
    sess = await get_active_session(db, x_session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or inactive session.")
    chats = await list_chats_for_session(db, x_session_id)
    return [{"chat_id": c.chat_id, "title": c.title} for c in chats]


@router.get("/chat-history/{chat_id}")
async def get_chat_history(
    chat_id: str,
    x_session_id: str | None = Header(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing x-session-id header.")
    sess = await get_active_session(db, x_session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or inactive session.")

    # NOTE: Ownership enforcement (chat belongs to session) is recommended but not implemented yet.
    offset = (page - 1) * page_size
    res = await db.execute(
        select(AmbioAiChatHistory)
        .where(AmbioAiChatHistory.chat_id == chat_id)
        .order_by(AmbioAiChatHistory.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    msgs = list(res.scalars().all())
    return [
        {
            "role": m.role,
            "mode": m.mode,
            "content": m.content,
            "meta": m.meta,
            "created_at": m.created_at,
        }
        for m in msgs
    ]

