from pydantic import BaseModel
from app.dto.req.chat_req import ChatReq

class ChatRequest(ChatReq):
    pass

class ChatResponse(BaseModel):
    response: str
