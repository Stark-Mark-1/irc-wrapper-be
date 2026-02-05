from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ambio_ai_strategy.generator_strategy import GeneratorStrategy
from app.llm_services.domain_llm_wrapper import DomainLlmWrapper
from app.models.ambio_ai_chat import AmbioAiChat
from app.models.enums import ChatRole, ReferenceType
from app.utils.database_utils.chat_history_utils import (
    count_user_messages_for_session_by_mode,
    create_chat_message,
    get_chat_history_by_chat_id,
)


class ChatStrategy(GeneratorStrategy):
    def purpose(self) -> list[str]:
        return ["chat"]

    async def run_validation(self, db: AsyncSession, session_id: str, reference_type: ReferenceType) -> bool:
        used = await count_user_messages_for_session_by_mode(db, session_id, "chat")
        if reference_type == ReferenceType.SIGNED_IN_USER:
            return used <= 3
        return used <= 1

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
        # Persist user message first
        user_msg = await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.USER,
            mode="chat",
            content=input_text,
            meta=None,
            previous_message_id=None,
        )

        # Build prior conversation for the model
        history = await get_chat_history_by_chat_id(db, active_chat.chat_id)
        model_messages: list[dict] = []
        for m in history:
            if m.role == ChatRole.USER:
                model_messages.append({"role": "user", "content": m.content})
            elif m.role == ChatRole.ASSISTANT:
                model_messages.append({"role": "assistant", "content": m.content})

        llm = DomainLlmWrapper()
        full = ""
        async for token in llm.stream_chat(model_messages):
            full += token
            yield token

        await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.ASSISTANT,
            mode="chat",
            content=full,
            meta={"provider": llm.llm_name(), "model": "text", "master_prompt": "applied"},
            previous_message_id=user_msg.chat_history_id,
        )

