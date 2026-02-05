from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReferenceType
from app.database.database import get_db
from app.utils.database_utils.session_utils import create_anonymous_session, create_signed_in_session

router = APIRouter()


@router.post("/session")
async def create_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None),
):
    # Minimal "signed-in" bootstrap: if client passes x-user-id, we create a SIGNED_IN_USER session.
    # Replace this with JWT validation when ready.
    user_agent = request.headers.get("user-agent")
    accept_language = request.headers.get("accept-language")
    client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else None)

    if x_user_id:
        sess = await create_signed_in_session(db=db, user_id=x_user_id)
        return {"session_id": sess.session_id, "user_type": "authenticated", "reference_type": sess.reference_type.value}

    sess = await create_anonymous_session(db=db, user_agent=user_agent, accept_language=accept_language, client_ip=client_ip)
    return {"session_id": sess.session_id, "user_type": "anonymous", "reference_type": sess.reference_type.value}

