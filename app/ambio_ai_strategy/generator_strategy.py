from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ambio_ai_chat import AmbioAiChat
from app.models.enums import ReferenceType


class GeneratorStrategy(ABC):
    @abstractmethod
    def purpose(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def run_validation(self, db: AsyncSession, session_id: str, reference_type: ReferenceType) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_response_content_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_response(
        self,
        *,
        input_text: str,
        active_chat: AmbioAiChat,
        session_id: str,
        db: AsyncSession,
        extra: dict | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError

