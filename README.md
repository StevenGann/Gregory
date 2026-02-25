# Gregory — Smart House AI

Gregory is an AI-powered glue layer that connects various interfaces and automations. His main interface is an HTTP API for chatting, with integrations for Home Assistant, Jellyfin, and multiple AI backends.

## Features

- **HTTP API** — Chat with Gregory via REST; future apps can use this for voice, web, and more
- **User-scoped chat** — Each family member has a dedicated conversation and notes
- **Notes** — Gregory maintains Markdown notes per user and for the household
- **AI backends** — Ollama (on-prem), Claude, Gemini (multi-provider routing coming in Phase 2)
- **Docker deployment** — Run on home server, Raspberry Pi, or anywhere

## Quick Start

### Docker (recommended)

1. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   # Edit OLLAMA_BASE_URL, FAMILY_MEMBERS, etc.
   ```

2. Run with Docker Compose:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

3. Gregory will be available at `http://localhost:8000`
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

### Local development

1. Create a virtual environment and install:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -e ".[dev]"
   ```

2. Set environment variables (or use `.env`):
   ```bash
   export OLLAMA_BASE_URL=http://localhost:11434
   export NOTES_PATH=./notes
   export FAMILY_MEMBERS=alice,bob,kids
   ```

3. Run:
   ```bash
   uvicorn gregory.main:app --reload --host 0.0.0.0 --port 8000
   ```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/users` | GET | List family members |
| `/users/{user_id}/chat` | POST | Send message, get response |

### Chat example

```bash
curl -X POST "http://localhost:8000/users/alice/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Gregory!"}'
```

Response:
```json
{
  "response": "Hello Alice! How can I help you today?",
  "conversation_id": "conv_1"
}
```

## Notes

Notes are stored in the `notes/` directory (or `NOTES_PATH`). In Docker, mount a volume:

```yaml
volumes:
  - ./notes:/app/notes
```

- `household.md` — General household notes (shared context)
- `{user_id}.md` — Per-user notes (e.g. `alice.md`, `bob.md`)

Gregory reads these before each chat and can append observations as he learns.

## Configuration

| Variable | Purpose |
|----------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL (e.g. `http://192.168.1.x:11434`) |
| `NOTES_PATH` | Path to notes directory |
| `FAMILY_MEMBERS` | Comma-separated user IDs |
| `LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR |

## Raspberry Pi

For ARM builds, use buildx:

```bash
docker buildx build --platform linux/arm64 -t gregory:latest -f docker/Dockerfile .
```

Or build on the Pi directly (may be slow).
