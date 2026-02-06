from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ambio_ai_strategy.generator_strategy import GeneratorStrategy
from app.models.ambio_ai_chat import AmbioAiChat
from app.models.enums import ChatRole, ReferenceType
from app.utils.database_utils.chat_history_utils import (
    count_user_messages_for_session_by_mode,
    create_chat_message,
)


class ImageStrategy(GeneratorStrategy):
    """
    Strategy for image generation mode.

    Note: This is a stubbed implementation. Image generation is not
    actually implemented - it returns a placeholder response.
    """

    def purpose(self) -> list[str]:
        return ["image"]

    async def run_validation(self, db: AsyncSession, session_id: str, reference_type: ReferenceType) -> bool:
        # Image generation is only available to signed-in users
        if reference_type != ReferenceType.SIGNED_IN_USER:
            return False
        used = await count_user_messages_for_session_by_mode(db, session_id, "image")
        return used < 3

    def get_response_content_type(self) -> str:
        return "application/json"

    async def generate_response(
        self,
        *,
        input_text: str,
        active_chat: AmbioAiChat,
        session_id: str,
        db: AsyncSession,
        extra: dict | None = None,
    ) -> AsyncIterator[str]:
        # Persist user message
        user_msg = await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.USER,
            mode="image",
            content=input_text,
            meta=None,
            previous_message_id=None,
        )

        # Stubbed response - image generation not implemented
        stub_response = (
            '{"status": "stub", "message": "Image generation is not implemented. '
            'This is a placeholder response.", "image_url": null}'
        )

        # Persist assistant message
        await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.ASSISTANT,
            mode="image",
            content=stub_response,
            meta={"provider": "stub", "model": "none", "status": "not_implemented"},
            previous_message_id=user_msg.chat_history_id,
        )

        yield stub_response
