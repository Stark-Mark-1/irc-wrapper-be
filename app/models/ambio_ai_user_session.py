from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import ReferenceType


class AmbioAiUserSession(Base):
    __tablename__ = "ambio_ai_user_session"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    unique_reference_id: Mapped[str] = mapped_column(String(256), index=True)
    reference_type: Mapped[ReferenceType] = mapped_column(Enum(ReferenceType), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

