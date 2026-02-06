from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_identifier(request: Request) -> str:
    """
    Get a unique identifier for the client.

    Uses x-session-id if available, otherwise falls back to IP address.
    """
    session_id = request.headers.get("x-session-id")
    if session_id:
        return f"session:{session_id}"
    return get_remote_address(request)


# Create the limiter instance
limiter = Limiter(key_func=get_client_identifier)
