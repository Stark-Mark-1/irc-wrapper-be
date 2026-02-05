from __future__ import annotations

import enum


class ReferenceType(str, enum.Enum):
    SIGNED_IN_USER = "SIGNED_IN_USER"
    NON_SIGNED_IN_USER = "NON_SIGNED_IN_USER"


class ChatRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SUMMARY = "SUMMARY"

