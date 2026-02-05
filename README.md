# IRC-AI Backend (Chat + Image Analysis)

FastAPI backend that supports:

- Session creation (`POST /api/v1/session`)
- Streaming chat (`POST /api/v1/chat`, `mode="chat"`)
- Streaming image analysis (`POST /api/v1/chat`, `mode="image_analysis"`)
- Chat history listing + retrieval

## Run locally

1) Create and activate a virtualenv, then install deps:

```bash
pip install -r requirements.txt
```

2) Create a `.env` (optional) with:

```bash
DATABASE_URL=sqlite+aiosqlite:///./app.db
OPENAI_API_KEY=...
MASTER_PROMPT=You are an assistant that only responds in the <your-domain> domain...
ALLOWED_CORS_ORIGINS=http://localhost:3000
```

3) Start the server:

```bash
uvicorn app.main:app --reload
```

Open docs at `http://127.0.0.1:8000/docs`.

## Quick usage

1) Create a session:
- Anonymous: `POST /api/v1/session`
- Signed-in (enables `mode=image_analysis` by default): add header `x-user-id: <any-user-id>`

2) Chat:
- `POST /api/v1/chat` with header `x-session-id: <session_id>` and JSON body `{ "mode": "chat", "prompt": "..." }`

3) Image analysis:
- `POST /api/v1/chat` with header `x-session-id: <session_id>` and body:
  - `{ "mode": "image_analysis", "prompt": "Describe this image", "image_url": "https://..." }`
  - or `{ "mode": "image_analysis", "prompt": "...", "image_base64": "<base64>" }`

