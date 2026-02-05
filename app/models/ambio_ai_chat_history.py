from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import ChatRole


class AmbioAiChatHistory(Base):
    __tablename__ = "ambio_ai_chat_history"

    chat_history_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id: Mapped[str] = mapped_column(String(64), index=True)
    previous_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole), index=True)
    mode: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

