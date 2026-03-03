from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.rehab_ai_strategy.generator_strategy import GeneratorStrategy
from app.llm_services.domain_llm_wrapper import DomainLlmWrapper
from app.models.rehab_ai_chat import RehabAiChat
from app.models.enums import ChatRole, ReferenceType
from app.utils.database_utils.chat_history_utils import (
    count_user_messages_for_session_by_mode,
    create_chat_message,
    get_chat_history_by_chat_id,
)


class FileAnalysisStrategy(GeneratorStrategy):
    def purpose(self) -> list[str]:
        return ["file_analysis"]

    async def run_validation(self, db: AsyncSession, session_id: str, reference_type: ReferenceType) -> bool:
        # File analysis for both signed-in and anonymous users
        used = await count_user_messages_for_session_by_mode(db, session_id, "file_analysis")
        return used < 100  # Allow up to 100 file analyses per session

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
        extra = extra or {}
        file_bytes: bytes | None = extra.get("file_bytes")
        file_type: str | None = extra.get("file_type")

        if not file_bytes or not file_type:
            yield "Error: file_bytes and file_type are required for file analysis."
            return

        meta: dict[str, Any] = {
            "file_type": file_type,
            "file_source": "multipart",
        }
        
        # Store hash of file content for audit trail
        meta["file_sha256"] = hashlib.sha256(file_bytes).hexdigest()

        user_msg = await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.USER,
            mode="file_analysis",
            content=input_text,
            meta=meta,
            previous_message_id=None,
        )

        # Include prior text-only messages as context
        history = await get_chat_history_by_chat_id(db, active_chat.chat_id)
        prior: list[dict[str, Any]] = []
        for m in history:
            if m.role == ChatRole.USER and m.mode == "chat":
                prior.append({"role": "user", "content": m.content})
            elif m.role == ChatRole.ASSISTANT and m.mode == "chat":
                prior.append({"role": "assistant", "content": m.content})

        llm = DomainLlmWrapper()
        full = ""
        async for token in llm.stream_file_analysis(
            prompt=input_text,
            file_bytes=file_bytes,
            file_type=file_type,
            prior_messages=prior,
        ):
            full += token
            yield token

        await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.ASSISTANT,
            mode="file_analysis",
            content=full,
            meta={
                "provider": llm.llm_name(),
                "model": llm.text_model_name(),
                "master_prompt": "applied",
            },
            previous_message_id=user_msg.chat_history_id,
        )
