from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.database import get_db
from app.utils.database_utils.session_utils import (
    create_anonymous_session,
    create_signed_in_session,
    get_active_session,
    invalidate_session,
)
from app.utils.jwtutils import extract_bearer_token, validate_token
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/session")
@limiter.limit(settings.rate_limit_session)
async def create_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    """
    Create or retrieve a session.

    Authentication methods (in order of precedence):
    1. Authorization: Bearer <jwt> - JWT with userId claim
    2. x-user-id header - Direct user ID (for development/testing)
    3. Anonymous - Fingerprint-based session
    """
    user_agent = request.headers.get("user-agent")
    accept_language = request.headers.get("accept-language")
    client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else None)

    # Try JWT authentication first
    token = extract_bearer_token(authorization)
    if token:
        payload = validate_token(token)
        if payload:
            logger.info(f"JWT authenticated user: {payload.user_id}")
            sess = await create_signed_in_session(db=db, user_id=payload.user_id)
            return {
                "session_id": sess.session_id,
                "user_type": "authenticated",
                "reference_type": sess.reference_type.value,
            }
        else:
            logger.warning("Invalid JWT token provided, falling back to anonymous")

    # Fall back to x-user-id header (for development/testing)
    if x_user_id:
        logger.info(f"x-user-id authenticated user: {x_user_id}")
        sess = await create_signed_in_session(db=db, user_id=x_user_id)
        return {
            "session_id": sess.session_id,
            "user_type": "authenticated",
            "reference_type": sess.reference_type.value,
        }

    # Create anonymous session
    sess = await create_anonymous_session(
        db=db,
        user_agent=user_agent,
        accept_language=accept_language,
        client_ip=client_ip,
    )
    return {
        "session_id": sess.session_id,
        "user_type": "anonymous",
        "reference_type": sess.reference_type.value,
    }


@router.delete("/session")
async def delete_session(
    x_session_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Invalidate the current session (logout).

    Requires x-session-id header.
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing x-session-id header.")

    # Verify session exists and is active
    sess = await get_active_session(db, x_session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or inactive session.")

    # Invalidate the session
    await invalidate_session(db, x_session_id)
    logger.info(f"Session invalidated: {x_session_id}")

    return {"message": "Session invalidated successfully."}
