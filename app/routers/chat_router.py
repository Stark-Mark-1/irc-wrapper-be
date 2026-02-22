

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.database import get_db
from app.models.rehab_ai_chat import RehabAiChat
from app.models.rehab_ai_chat_history import RehabAiChatHistory
from app.models.rehab_ai_user_session import RehabAiUserSession
from app.models.enums import ChatRole
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.rehab_ai_strategy.choose_strategy import choose_strategy
from app.rehab_ai_strategy.strategy_register import register_strategies  # noqa: F401

from app.utils.database_utils.chat_utils import get_or_create_chat
from app.utils.database_utils.session_utils import get_active_session
from app.utils.rate_limiter import limiter

router = APIRouter()


@router.post("/chat")
@limiter.limit(settings.rate_limit_chat)
async def chat(
    request: Request,
    body: ChatRequest,
    x_session_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing x-session-id header.")

    sess = await get_active_session(db, x_session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or inactive session.")

    strategy = choose_strategy(body.mode)
    ok = await strategy.run_validation(db, x_session_id, sess.reference_type)
    if not ok:
        raise HTTPException(status_code=403, detail="Usage limit or access tier violated.")

    active_chat = await get_or_create_chat(db=db, session_id=x_session_id, chat_id=body.chat_id, prompt=body.prompt)

    async def gen():
        async for chunk in strategy.generate_response(
            input_text=body.prompt,
            active_chat=active_chat,
            session_id=x_session_id,
            db=db,
            extra={"image_url": body.image_url, "image_base64": body.image_base64},
        ):
            yield chunk

    resp = StreamingResponse(gen(), media_type=strategy.get_response_content_type())
    resp.headers["X-Chat-Id"] = active_chat.chat_id
    resp.headers["X-Content-Type"] = strategy.get_response_content_type()
    return resp


@router.post("/chat/file")
@limiter.limit(settings.rate_limit_chat)
async def chat_file(
    request: Request,
    prompt: str = Form(..., min_length=1, max_length=10000),
    chat_id: str | None = Form(default=None),
    file: UploadFile | None = File(...),
    x_session_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing x-session-id header.")

    sess = await get_active_session(db, x_session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or inactive session.")

    if not file:
        raise HTTPException(status_code=400, detail="file is required for /chat/file endpoint.")

    # Read file content
    file_bytes = await file.read()
    file_type = None
    
    # Extract file type from filename
    if file.filename:
        file_ext = file.filename.split(".")[-1].lower()
        if file_ext in ["pdf", "jpeg", "jpg", "png"]:
            file_type = file_ext
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Supported: pdf, jpeg, jpg, png")
    
    if not file_type:
        raise HTTPException(status_code=400, detail="Could not determine file type from filename.")

    strategy = choose_strategy("file_analysis")
    ok = await strategy.run_validation(db, x_session_id, sess.reference_type)
    if not ok:
        raise HTTPException(status_code=403, detail="Usage limit or access tier violated.")

    active_chat = await get_or_create_chat(db=db, session_id=x_session_id, chat_id=chat_id, prompt=prompt)

    async def gen():
        async for chunk in strategy.generate_response(
            input_text=prompt,
            active_chat=active_chat,
            session_id=x_session_id,
            db=db,
            extra={
                "file_bytes": file_bytes,
                "file_type": file_type,
            },
        ):
            yield chunk

    resp = StreamingResponse(gen(), media_type=strategy.get_response_content_type())
    resp.headers["X-Chat-Id"] = active_chat.chat_id
    resp.headers["X-Content-Type"] = strategy.get_response_content_type()
    return resp

