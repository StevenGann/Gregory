# Debug UI

Static HTML utilities for testing and debugging Gregory.

## Files

| File | Purpose |
|------|---------|
| `chat.html` | Chat interface — send messages and view responses |
| `config.html` | Config viewer/editor — view and edit `config.json` (secrets masked) |
| `logging.html` | Log viewer — stream logs via Server-Sent Events with filters |

## Running

**Option 1: Python HTTP server**

```bash
cd debug
python -m http.server 8080
```

Then open:
- http://localhost:8080/chat.html
- http://localhost:8080/config.html
- http://localhost:8080/logging.html

**Option 2: Windows — run.bat**

From the project root, run `run.bat`. It starts:
- Debug UI server on port 8080
- Gregory API (uvicorn) on port 8000

## Requirements

- Gregory API must be running on the configured base URL (default: http://localhost:8000)
- Serve the debug UI over HTTP — do not open files directly (`file://`) due to CORS restrictions

## API Endpoints Used

The debug UI calls these endpoints:

- `GET /users` — List family members (chat)
- `POST /users/{user_id}/chat` — Send messages (chat)
- `GET /debug/logs` — Recent logs (logging)
- `GET /debug/logs/stream` — Live log stream (logging)
- `GET /debug/config` — Config with masked secrets (config)
- `PATCH /debug/config` — Update config (config)

See [API Reference](../docs/API.md#debug-api) for details.
