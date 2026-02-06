from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenPayload:
    user_id: str
    claims: dict[str, Any]


def validate_token(token: str) -> TokenPayload | None:
    """
    Validate a JWT token and extract the payload.

    Args:
        token: The JWT token string (without "Bearer " prefix)

    Returns:
        TokenPayload with user_id and claims if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )
        user_id = payload.get("userId") or payload.get("user_id") or payload.get("sub")
        if not user_id:
            logger.warning("JWT missing userId/user_id/sub claim")
            return None

        return TokenPayload(user_id=str(user_id), claims=payload)

    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


def extract_bearer_token(authorization_header: str | None) -> str | None:
    """
    Extract the token from a Bearer authorization header.

    Args:
        authorization_header: The full Authorization header value

    Returns:
        The token string if valid Bearer format, None otherwise
    """
    if not authorization_header:
        return None

    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]
