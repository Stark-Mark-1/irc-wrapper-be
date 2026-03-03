from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from app.rehab_ai_strategy.generator_strategy import GeneratorStrategy
from app.llm_services.domain_llm_wrapper import DomainLlmWrapper
from app.models.rehab_ai_chat import RehabAiChat
from app.models.rehab_ai_chat_history import RehabAiChatHistory
from app.models.rehab_ai_prompts import RehabAiPrompts
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
            return used <= 100
        return used <= 100

    def get_response_content_type(self) -> str:
        return "text/plain"

    async def generate_response(
        self,
        *,
        input_text: str,
        active_chat: RehabAiChat,
        session_id: str,
        db: AsyncSession,
        extra: dict | None = None,
    ) -> AsyncIterator[str]:
        # 1. Fetch system prompt
        system_prompt_db = await db.scalar(
            select(RehabAiPrompts).where(RehabAiPrompts.name == "master_prompt")
        )
        system_prompt = system_prompt_db.content if system_prompt_db else settings.master_prompt

        # 2. Fetch history
        # We need to fetch history for this chat
        history_objs = await get_chat_history_by_chat_id(db, active_chat.chat_id)

        messages = []
        for msg in history_objs:
            messages.append({"role": msg.role.value.lower(), "content": msg.content})

        # Add current user message
        messages.append({"role": "user", "content": input_text})

        # 3. Call LLM
        # We'll use a streaming response from the LLM service
        full_response = ""
        llm = DomainLlmWrapper(master_prompt=system_prompt)
        async for chunk in llm.stream_chat(messages): # Assuming generate_response_stream is stream_chat
            yield chunk
            full_response += chunk

        # 4. Save history
        # Save user message
        await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.USER,
            mode=self.purpose()[0], # Assuming strategy_name() is purpose()[0]
            content=input_text,
        )
        # Save assistant message
        await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.ASSISTANT,
            mode=self.purpose()[0], # Assuming strategy_name() is purpose()[0]
            content=full_response,
        )
