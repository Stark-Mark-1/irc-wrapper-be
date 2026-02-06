from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Any

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


class ImageAnalysisStrategy(GeneratorStrategy):
    def purpose(self) -> list[str]:
        return ["image_analysis"]

    async def run_validation(self, db: AsyncSession, session_id: str, reference_type: ReferenceType) -> bool:
        # Match prior ImageStrategy behavior: signed-in only by default.
        if reference_type != ReferenceType.SIGNED_IN_USER:
            return False
        used = await count_user_messages_for_session_by_mode(db, session_id, "image_analysis")
        return used < 3

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
        extra = extra or {}
        image_url: str | None = extra.get("image_url")
        image_base64: str | None = extra.get("image_base64")

        meta: dict[str, Any] = {"image_source": "url" if image_url else "base64"}
        if image_url:
            meta["image_url"] = image_url
            meta["image_sha256"] = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
        else:
            # Store only hash, never raw base64
            b64 = image_base64 or ""
            meta["image_sha256"] = hashlib.sha256(b64.encode("utf-8")).hexdigest()

        user_msg = await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.USER,
            mode="image_analysis",
            content=input_text,
            meta=meta,
            previous_message_id=None,
        )

        # Optional: include prior text-only messages as context
        history = await get_chat_history_by_chat_id(db, active_chat.chat_id)
        prior: list[dict[str, Any]] = []
        for m in history:
            if m.role == ChatRole.USER and m.mode == "chat":
                prior.append({"role": "user", "content": m.content})
            elif m.role == ChatRole.ASSISTANT and m.mode == "chat":
                prior.append({"role": "assistant", "content": m.content})

        llm = DomainLlmWrapper()
        full = ""
        async for token in llm.stream_image_analysis(
            prompt=input_text,
            image_url=image_url,
            image_base64=image_base64,
            prior_messages=prior,
        ):
            full += token
            yield token

        await create_chat_message(
            db=db,
            chat_id=active_chat.chat_id,
            role=ChatRole.ASSISTANT,
            mode="image_analysis",
            content=full,
            meta={"provider": llm.llm_name(), "model": llm.vision_model_name(), "master_prompt": "applied"},
            previous_message_id=user_msg.chat_history_id,
        )

