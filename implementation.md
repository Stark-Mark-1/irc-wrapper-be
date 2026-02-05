# Ambio AI Backend — How It Works + Spec for a New AI Wrapper (Chat + Image Analysis)

This document is meant to be **standalone**: it explains how the current backend works (request flow, routers, strategies, services, DB models), **how it connects to models**, **how it handles security**, and it provides a complete **design/spec for a new AI wrapper** that does the same core things but with **chat + image analysis** (no image generation).

---

## 1) What this backend is

This repo is a FastAPI backend that exposes a small API surface:

- **Session creation** (`POST /api/v1/session`)
- **Chat streaming** (`POST /api/v1/chat`) with a `mode` that selects behavior
- **Chat history retrieval** (`GET /api/v1/chat-history` and `GET /api/v1/chat-history/{chat_id}`)
- **Prompt templates** (`PUT /api/v1/prompts`, `GET /api/v1/prompts`)

The core design choice is a **Strategy pattern**:

- Each request to `/chat` provides a `mode` (e.g. `"chat"`, `"image"`).
- The backend selects a `GeneratorStrategy` implementation for that mode.
- The strategy:
  - validates usage limits (and sometimes role requirements)
  - persists the user message
  - generates an assistant response (streaming or non-streaming)
  - persists the assistant response

Key files:

- App wiring: `app/main.py`
- Routers: `app/routers/*.py`
- Strategies: `app/ambio_ai_strategy/*.py`
- LLM services: `app/llm_services/*.py`
- DB config: `app/database/database.py`
- Models: `app/models/*.py`
- DB utilities: `app/utils/database_utils/*.py`
- JWT/admin token utils: `app/utils/jwtutils.py`

---

## 2) Request lifecycle (end-to-end)

### 2.1 Startup / app initialization

`app/main.py`:

- Loads env vars (`dotenv.load_dotenv()`).
- Configures CORS from `ALLOWED_CORS_ORIGINS`.
- Registers exception handlers (`HTTPException`, `ValidationError`, `SQLAlchemyError`, generic `Exception`).
- Includes routers under `/api/v1`:
  - `/session`
  - `/prompts`
  - `/chat-history`
  - `/chat`

### 2.2 `POST /api/v1/session` — create/get session

Router: `app/routers/session_router.py`

Inputs:

- **Optional** `Authorization: Bearer <jwt>`

Behavior:

1. If `Authorization` is present:
   - `validate_token()` decodes the JWT using `SECRET_KEY` (HS256).
   - Extracts `claims["userId"]`.
   - Looks up the user by `userId` (`find_user_by_userid()`).
   - If user exists: creates/reuses a **signed-in session** (`create_session_by_user()`).
2. Otherwise (no header, invalid/expired JWT, user not found, etc.):
   - Creates/reuses an **anonymous session** (`create_anonymous_session()`).

Outputs:

- Always returns `session_id` and a `user_type` flag (`"authenticated"` or `"anonymous"`).

How anonymous session identity is created:

- `session_utils._generate_fingerprint()` hashes:
  - `user-agent`
  - `accept-language`
  - client IP (prefers `x-forwarded-for` if present)

This becomes `AmbioAiUserSession.unique_reference_id` for anonymous users.

### 2.3 `POST /api/v1/chat` — chat streaming

Router: `app/routers/chat_router.py`

Inputs:

- Required header: `x-session-id: <session_id>`
- Body (`app/dto/req/ChatReq.py`):

```json
{
  "chat_id": "optional",
  "mode": "chat | image | ...",
  "prompt": "string"
}
```

Behavior:

1. Validates `x-session-id` header is present.
2. Validates session exists and `is_active = true`:
   - `check_session_validity_then_return_session(session_id, db)`
3. Chooses a strategy by `mode`:
   - `choose_strategy(body.mode)` from `app/ambio_ai_strategy/startegy_register.py`
4. Runs usage/role validation:
   - `await strategy.run_validation(db, session_id, user_session.reference_type)`
5. Gets or creates chat thread:
   - `get_or_create_chat(chat_id, db, session_id, prompt)`
   - If new, `title = prompt[:50]`
6. Builds a response generator:
   - `strategy.generate_response(prompt, active_chat, session_id, db)`
7. Returns a `StreamingResponse` and exposes headers:
   - `X-Chat-Id: <active_chat.chat_id>`
   - `X-Content-Type: <strategy.get_response_content_type()>`

Persistence behavior (important):

- For `ChatStrategy` (text chat): user message is persisted **before** model call; assistant response is persisted **after** streaming completes (as one concatenated string).
- For `ImageStrategy`: user message is persisted, then a stubbed image response is persisted and returned.

### 2.4 `GET /api/v1/chat-history` — list chats for session

Router: `app/routers/history_router.py`

Inputs:

- Required header: `x-session-id`

Behavior:

- Validates session as above.
- Lists chats in `AmbioAiChat` where:
  - `session_id == x-session-id`
  - `is_archived == false`
- Returns `chat_id` + `title`

### 2.5 `GET /api/v1/chat-history/{chat_id}` — paginated messages

Inputs:

- Required header: `x-session-id`
- Path param: `chat_id`
- Query params:
  - `page` (default 1, min 1)
  - `page_size` (default 10, min 1, max 100)

Behavior:

- Validates session.
- Fetches messages from `AmbioAiChatHistory` for that `chat_id`:
  - ordered newest-first (DB query)
  - returns `role`, `content`, `created_at`

### 2.6 `/api/v1/prompts` — prompt templates

Router: `app/routers/prompt_router.py`

Endpoints:

- `PUT /api/v1/prompts`
  - Requires header `x-token`
  - `validate_admin_token(token)` must equal env var `ADMIN_API_TOKEN`
  - Inserts rows into `AmbioAiPrompts`
- `GET /api/v1/prompts`
  - Returns all non-archived prompts from `AmbioAiPrompts`

---

## 3) How the backend “connects to models”

The model access layer is in `app/llm_services/`.

### 3.1 The LLM interface

`app/llm_services/llm_service.py` defines `LlmService`:

- `generate_response_stream(messages) -> AsyncIterator[str]`
- `custom_prompt() -> str`
- `llm_name() -> str`

### 3.2 OpenAI implementation (streaming)

`app/llm_services/openai_service.py`:

- Uses `AsyncOpenAI(api_key=OPENAI_API_KEY)`
- Calls:
  - `client.chat.completions.create(model="gpt-4o", messages=[...], stream=True)`
- Iterates chunks and yields `delta.content` strings as they arrive

The “system behavior” prompt is embedded in `OpenAIService.custom_prompt()` (a large “developer” message).

### 3.3 Z.ai implementation (non-streaming wrapped as stream)

`app/llm_services/zai_service.py`:

- Uses `httpx.AsyncClient` to call `https://api.z.ai/api/paas/v4/chat/completions`
- Sends `stream: False`
- Then yields the full response content once

### 3.4 Where LLM services are used today

`ChatStrategy` (`app/ambio_ai_strategy/chat_strategy.py`) uses `OpenAIService()` directly.

Notes:

- It fetches prior messages from DB and appends them to the model messages.
- It adds a `developer` message with the custom prompt.
- It streams tokens to the client and accumulates them into `full_response` for persistence.

`ImageStrategy` (`app/ambio_ai_strategy/image_strategy.py`) does **not** call any real image model right now; it returns a stub response and a stub image URL in `meta`.

---

## 4) How strategies and the registry work

### 4.1 Strategy contract

`app/ambio_ai_strategy/generator_strategy.py` defines `GeneratorStrategy`:

- `generate_response(input_text, active_chat, session_id, session) -> AsyncIterator[str]`
- `purpose() -> list[str]` (mode aliases)
- `run_validation(session, session_id, user_role) -> bool`
- `get_response_content_type() -> str`

### 4.2 Registry and dispatch

- Registry dict: `app/ambio_ai_strategy/registry.py` (`STRATEGY_REGISTRY: Dict[str, Type[GeneratorStrategy]]`)
- Registration happens at import time in `app/ambio_ai_strategy/startegy_register.py`:
  - `register_strategies(ChatStrategy, ImageStrategy)`
- Dispatch:
  - If no mode: default to `ChatStrategy()`
  - If unknown mode: `BadStrategy(invalid_mode=mode)`
  - Else: instantiate the registered strategy class

### 4.3 Current modes

- `ChatStrategy.purpose() -> ["chat"]`
- `ImageStrategy.purpose() -> ["image"]`

---

## 5) Data model (tables) and how persistence works

Database is SQLAlchemy async (`create_async_engine` + `AsyncSession`).

Configured in `app/database/database.py`:

- `DATABASE_URL` must be set
- `ECHO_SQL` optional
- Pool: `NullPool`

### 5.1 `AmbioAiUserSession` — session identity layer

File: `app/models/ambio_ai_user_session.py`

Key columns:

- `session_id` (UUID string)
- `unique_reference_id` (string)
  - signed-in: `user.user_id`
  - anonymous: fingerprint hash
- `reference_type` enum:
  - `SIGNED_IN_USER`
  - `NON_SIGNED_IN_USER`
- `is_active` (bool)

### 5.2 `AmbioAiChat` — chat threads

File: `app/models/ambio_ai_chat.py`

Key columns:

- `chat_id` (UUID string)
- `session_id` (string, links to session_id)
- `title` (string, created from first prompt truncated to 50 chars)
- `is_archived` (bool)

### 5.3 `AmbioAiChatHistory` — all messages

File: `app/models/ambio_ai_chat_history.py`

Key columns:

- `chat_history_id` (UUID string)
- `chat_id` (string)
- `previous_message_id` (string or null)
- `role` enum:
  - `USER`
  - `ASSISTANT`
  - `SUMMARY` (not currently used in strategies)
- `mode` (string, e.g. `"chat"`, `"image"`)
- `content` (text)
- `meta` (JSON dict, optional)

### 5.4 How messages are written

`app/utils/database_utils/chat_history_utils.py`:

- `create_chat_message(...)` inserts into `AmbioAiChatHistory`, commits, refreshes, returns object.
- `get_chat_history_by_chat_id(chat_id)` returns all messages ordered by `created_at` ascending (oldest-first).
- Pagination helper returns newest-first for history endpoint.

### 5.5 Usage limits (per strategy)

In each strategy’s `run_validation()`:

- `ChatStrategy`:
  - Signed-in: allowed if user-message count (mode `"chat"`) \( \le 3 \)
  - Non-signed-in: allowed if count \( \le 1 \)
- `ImageStrategy`:
  - Non-signed-in: **always rejected**
  - Signed-in: allowed if user-message count (mode `"image"`) \( < 3 \)

Implementation detail:

- Both strategies count messages by scanning all chat_ids for the session and counting rows in `AmbioAiChatHistory` where:
  - `role == USER`
  - `mode == <strategy_mode>`

---

## 6) How the backend keeps data “secure” (what it does today)

This section describes **actual security controls implemented in code** today, and what they protect.

### 6.1 Secrets management

Secrets are pulled from environment variables:

- `DATABASE_URL`
- `SECRET_KEY` (JWT signing key)
- `ADMIN_API_TOKEN` (admin prompt write token)
- `OPENAI_API_KEY`, `ZAI_API_KEY`, etc.

The backend does **not** hardcode provider keys in source code.

### 6.2 Authentication and authorization

There are two parallel auth concepts:

1. **User authentication** (JWT):
   - Only used during session creation (`POST /session`)
   - `validate_token()` decodes HS256 JWT using `SECRET_KEY`
   - Extracts `userId` to look up a `User`
2. **Session authorization** (session_id):
   - All chat/history operations require `x-session-id`
   - Requests are authorized by verifying the session exists and `is_active=true`
   - Strategy validation uses the session’s `reference_type` as an access tier

Admin authorization:

- `PUT /prompts` requires header `x-token` to equal env var `ADMIN_API_TOKEN`

### 6.3 Data access boundaries

What is enforced:

- Chat listing uses `session_id` equality filter.
- Chat history retrieval validates the session exists **but does not verify that the requested `chat_id` belongs to that session**.
  - Today, `GET /chat-history/{chat_id}` fetches messages only by `chat_id`.
  - This is an important boundary: if an attacker can guess a valid `chat_id`, they may retrieve messages even from another session.

### 6.4 Transport security

- This codebase does not itself enforce HTTPS. In production, HTTPS must be enforced at the reverse proxy / load balancer.
- CORS is enabled and configured by `ALLOWED_CORS_ORIGINS`.

### 6.5 Injection and unsafe query risks

- ORM queries are used (SQLAlchemy), which provides parameterization and reduces classic SQL injection risk.

### 6.6 Sensitive content in logs

- JWT decode errors and session checks are logged.
- There is no explicit redaction layer for prompts or model outputs. If logging is expanded, avoid logging raw prompts/tokens.

### 6.7 Missing controls (recommended hardening)

If you want this backend to be stronger, the most important additions are:

- **Enforce chat ownership** on `GET /chat-history/{chat_id}` by verifying the chat belongs to `x-session-id`.
- **Rate limiting** (per IP/session/user) for `/session` and `/chat`.
- **Request size limits** (prompt size, image payload size).
- **Better admin auth** than static token equality (rotate, expiry, scoped permissions).
- **Audit logs** for admin actions and suspicious access patterns.
- **Session hijack defense** (invalidate sessions, rotate session_id on privilege changes).
- **Input sanitization** if prompts/outputs are rendered in a web UI (XSS prevention at frontend is typical; backend can also store raw but must ensure frontend escapes).

---

## 7) The “new AI wrapper” requirement

You requested:

- A wrapper that does the same things:
  - session-based access
  - chat with streaming
  - history persistence
- BUT instead of image generation, it must do **image analysis**:
  - input includes an image + optional text prompt
  - output is **textual analysis** (streamed if possible)
  - persist analysis and image reference in history

This section is a full implementation spec that matches this backend’s architecture.

---

## 8) New AI wrapper spec — Chat + Image Analysis (no image generation)

### 8.1 High-level architecture

Keep the same layering:

1. Router (`/chat`) accepts `mode` and dispatches to a strategy.
2. Strategy persists user input, calls an LLM “vision” service, streams analysis, persists assistant output.
3. DB schema stays the same; use `AmbioAiChatHistory.meta` JSON to store image reference and model metadata.

### 8.2 API contract (recommended)

Keep existing chat request as-is for text mode, and extend it for image analysis mode.

#### Endpoint: `POST /api/v1/chat`

Header:

- `x-session-id: <session_id>`

Body (extended DTO):

```json
{
  "chat_id": "optional",
  "mode": "chat | image_analysis",
  "prompt": "text prompt describing what to analyze / questions to answer",

  "image_url": "optional string",
  "image_base64": "optional string"
}
```

Rules:

- For `mode="chat"`:
  - `prompt` required, no image fields required
- For `mode="image_analysis"`:
  - `prompt` required (can be short like “Describe this image”)
  - exactly one of `image_url` or `image_base64` must be provided

Response:

- Continue using `StreamingResponse`.
- Headers:
  - `X-Chat-Id: <uuid>`
  - `X-Content-Type: text/plain`

### 8.3 Strategy design

Add a new strategy: `ImageAnalysisStrategy`.

File:

- `app/ambio_ai_strategy/image_analysis_strategy.py` (new)

Contract:

- `purpose() -> ["image_analysis"]` (or multiple aliases)
- `get_response_content_type() -> "text/plain"`
- `run_validation()`:
  - Decide policy. Two common options:
    - **Option A (match existing image policy)**: signed-in only, anonymous rejected.
    - **Option B**: allow anonymous but strict quota (e.g. 1) and strong rate limiting.
  - Count usage in `AmbioAiChatHistory` where `mode == "image_analysis"` and `role == USER`.
- `generate_response()`:
  - Load conversation context from DB (like `ChatStrategy`) if desired:
    - either include prior user/assistant messages
    - or only include the last N messages
  - Persist the **user message** with:
    - `mode="image_analysis"`
    - `meta` containing image reference (url/base64 hash, content type, etc.)
  - Call a vision-capable LLM service and stream analysis tokens.
  - Persist the **assistant message** with:
    - `mode="image_analysis"`
    - `meta` containing model name, provider, timing/tokens if available

### 8.4 Vision-capable model integration (service layer)

You have two clean choices.

#### Choice 1: Extend the existing OpenAI service

Add a method such as:

- `generate_vision_response_stream(messages_with_image) -> AsyncIterator[str]`

Where a “user” message includes image content. In OpenAI’s modern APIs this is typically structured content (text + image parts).

Implementation notes:

- Keep `OpenAIService.generate_response_stream(...)` for text chat.
- Add a separate method for vision requests so you don’t break existing callers.

#### Choice 2: Create a separate `VisionService` interface

Add:

- `app/llm_services/vision_service.py` (new ABC)
- Implement `OpenAIVisionService`, etc.

This is cleaner if you will support multiple providers for vision.

### 8.5 DB persistence format for image analysis

Use `AmbioAiChatHistory.meta` for structured data.

#### User message `meta` example

```json
{
  "image_source": "url",
  "image_url": "https://...",
  "image_sha256": "optional",
  "client_hints": {
    "filename": "optional",
    "mime": "optional"
  }
}
```

If using base64:

- Do **not** store raw base64 in DB unless you truly need it.
- Prefer storing a hash and (optionally) persisting the binary in object storage (S3/GCS) and storing a signed URL.

#### Assistant message `meta` example

```json
{
  "provider": "OpenAI",
  "model": "gpt-4o",
  "mode": "image_analysis",
  "latency_ms": 1234
}
```

### 8.6 Security requirements specific to image analysis

Image analysis introduces new risks and costs; include these controls:

- **Input limits**:
  - max image size (bytes)
  - max base64 length
  - max prompt length
- **URL fetching policy** (if `image_url` is accepted):
  - block private IP ranges (SSRF protection)
  - enforce allowed schemes (`https` only recommended)
  - enforce content-type allowlist (jpeg/png/webp)
  - enforce max download size and timeout
- **Storage policy**:
  - don’t log base64 or raw image bytes
  - if persisting images, store in object storage with short-lived signed URLs
- **Authorization**:
  - treat image analysis like `ImageStrategy` today (signed-in only) unless product requires otherwise
- **Rate limiting**:
  - stricter than text chat (vision is more expensive)

### 8.7 Changes needed in this codebase (concrete)

#### A) Extend the request DTO

Update `app/dto/req/ChatReq.py` to include image fields (optional).

#### B) Add and register strategy

- Add `app/ambio_ai_strategy/image_analysis_strategy.py`
- Register it in `app/ambio_ai_strategy/startegy_register.py`:
  - `register_strategies(ChatStrategy, ImageStrategy, ImageAnalysisStrategy)`

#### C) Update frontend/clients (contract implication)

Clients must:

- call `POST /api/v1/session` to obtain `session_id`
- include `x-session-id` on all chat/history calls
- call `/chat` with:
  - `mode="chat"` for text
  - `mode="image_analysis"` and image payload fields for analysis

### 8.8 Suggested behavior for analysis output (quality and format)

To make analysis useful and consistent, standardize the assistant output format:

- **Summary** (1–3 lines)
- **Observed details** (bullets)
- **Issues/risks** (if any)
- **Recommendations / next steps** (bullets)
- **Questions** (if the image is ambiguous)

This is application-level formatting guidance; the exact prompt can be embedded similarly to `OpenAIService.custom_prompt()`.

---

## 9) Compatibility notes vs current implementation

Important “as-is” behavior in this repo that your new wrapper should either mirror or deliberately change:

- **Streaming**:
  - `/chat` returns a `StreamingResponse` even if some providers aren’t truly streaming (e.g. `ZaiService` yields once).
- **History ownership check**:
  - `/chat-history/{chat_id}` currently does not enforce ownership by `x-session-id`. Fixing this is strongly recommended.
- **Usage limits**:
  - Current limits are very small (chat: 1/3; image: <3). Adjust as product requires, but keep the same counting approach per mode.
- **Image strategy is stubbed**:
  - Image generation isn’t actually implemented; your image analysis should be implemented for real.

---

## 10) Quick reference: current endpoints

- `POST /api/v1/session`
- `POST /api/v1/chat` (streaming)
- `GET /api/v1/chat-history`
- `GET /api/v1/chat-history/{chat_id}?page=1&page_size=10`
- `PUT /api/v1/prompts` (admin token via `x-token`)
- `GET /api/v1/prompts`

