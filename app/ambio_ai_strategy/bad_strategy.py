from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ambio_ai_strategy.generator_strategy import GeneratorStrategy
from app.models.ambio_ai_chat import AmbioAiChat
from app.models.enums import ReferenceType


class BadStrategy(GeneratorStrategy):
    def __init__(self, invalid_mode: str | None = None) -> None:
        self.invalid_mode = invalid_mode or "unknown"

    def purpose(self) -> list[str]:
        return []

    async def run_validation(self, db: AsyncSession, session_id: str, reference_type: ReferenceType) -> bool:
        return True

    def get_response_content_type(self) -> str:
        return "text/plain"

    async def generate_response(
        self,
        *,
        input_text: str,
        active_chat: AmbioAiChat,
        session_id: str,
        db: AsyncSession,
        extra: dict | None = None,
    ) -> AsyncIterator[str]:
        yield f"Invalid mode: {self.invalid_mode}"

