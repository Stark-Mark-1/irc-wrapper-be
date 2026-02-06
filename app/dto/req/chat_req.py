from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ChatReq(BaseModel):
    chat_id: str | None = None
    mode: str = Field(default="chat")
    prompt: str = Field(min_length=1, max_length=10000)

    # Image analysis inputs (mode=image_analysis)
    # max_length for base64: ~10MB image = ~13.3MB base64
    image_url: str | None = Field(default=None, max_length=2000)
    image_base64: str | None = Field(default=None, max_length=14_000_000)

    @model_validator(mode="after")
    def _validate_mode_and_image_inputs(self) -> "ChatReq":
        m = (self.mode or "chat").strip().lower()
        if m == "chat":
            return self
        if m == "image_analysis":
            has_url = bool(self.image_url)
            has_b64 = bool(self.image_base64)
            if has_url == has_b64:
                raise ValueError("For mode=image_analysis, provide exactly one of image_url or image_base64.")
            return self
        # allow other modes to be handled by BadStrategy
        return self

