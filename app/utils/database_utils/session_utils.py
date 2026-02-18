from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rehab_ai_user_session import RehabAiUserSession
from app.models.enums import ReferenceType


def _generate_fingerprint(user_agent: str | None, accept_language: str | None, client_ip: str | None) -> str:
    raw = f"{user_agent or ''}|{accept_language or ''}|{client_ip or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def create_anonymous_session(
    *,
    db: AsyncSession,
    user_agent: str | None,
    accept_language: str | None,
    client_ip: str | None,
) -> RehabAiUserSession:
    fingerprint = _generate_fingerprint(user_agent, accept_language, client_ip)
    existing = await db.scalar(
        select(RehabAiUserSession).where(
            RehabAiUserSession.unique_reference_id == fingerprint,
            RehabAiUserSession.reference_type == ReferenceType.NON_SIGNED_IN_USER,
            RehabAiUserSession.is_active.is_(True),
        )
    )
    if existing:
        return existing

    sess = RehabAiUserSession(
        session_id=str(uuid.uuid4()),
        unique_reference_id=fingerprint,
        reference_type=ReferenceType.NON_SIGNED_IN_USER,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def create_signed_in_session(*, db: AsyncSession, user_id: str) -> RehabAiUserSession:
    existing = await db.scalar(
        select(RehabAiUserSession).where(
            RehabAiUserSession.unique_reference_id == user_id,
            RehabAiUserSession.reference_type == ReferenceType.SIGNED_IN_USER,
            RehabAiUserSession.is_active.is_(True),
        )
    )
    if existing:
        return existing

    sess = RehabAiUserSession(
        session_id=str(uuid.uuid4()),
        unique_reference_id=user_id,
        reference_type=ReferenceType.SIGNED_IN_USER,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def get_active_session(db: AsyncSession, session_id: str) -> RehabAiUserSession | None:
    return await db.scalar(
        select(RehabAiUserSession).where(
            RehabAiUserSession.session_id == session_id,
            RehabAiUserSession.is_active.is_(True),
        )
    )


async def invalidate_session(db: AsyncSession, session_id: str) -> bool:
    """
    Invalidate a session by setting is_active to False.

    Returns:
        True if session was found and invalidated, False if not found
    """
    session = await db.scalar(
        select(RehabAiUserSession).where(RehabAiUserSession.session_id == session_id)
    )
    if not session:
        return False

    session.is_active = False
    await db.commit()
    return True


async def invalidate_all_sessions_for_user(db: AsyncSession, user_id: str) -> int:
    """
    Invalidate all sessions for a given user.

    Returns:
        Number of sessions invalidated
    """
    result = await db.execute(
        select(RehabAiUserSession).where(
            RehabAiUserSession.unique_reference_id == user_id,
            RehabAiUserSession.is_active.is_(True),
        )
    )
    sessions = list(result.scalars().all())

    for session in sessions:
        session.is_active = False

    await db.commit()
    return len(sessions)

