from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Ensure audit logs go to a separate handler if needed
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[AUDIT] %(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    audit_logger.addHandler(handler)


def log_admin_action(
    action: str,
    request: Request,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log an admin action for audit purposes.

    Args:
        action: Description of the action (e.g., "prompt_created", "prompt_updated")
        request: The FastAPI request object
        details: Additional details to log
    """
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )
    user_agent = request.headers.get("user-agent", "unknown")

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "path": str(request.url.path),
        "method": request.method,
    }

    if details:
        log_entry["details"] = details

    audit_logger.info(f"Admin action: {log_entry}")


def log_suspicious_access(
    reason: str,
    request: Request,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log a suspicious access pattern.

    Args:
        reason: Why this access is suspicious
        request: The FastAPI request object
        details: Additional details to log
    """
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )
    session_id = request.headers.get("x-session-id", "none")

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "client_ip": client_ip,
        "session_id": session_id,
        "path": str(request.url.path),
        "method": request.method,
    }

    if details:
        log_entry["details"] = details

    audit_logger.warning(f"Suspicious access: {log_entry}")
