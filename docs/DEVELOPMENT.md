# Development

## Setup

1. Clone the repository and create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

2. Install in editable mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

3. Copy `.env.example` to `.env` and configure at least one AI provider (`OLLAMA_BASE_URL`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`), plus `NOTES_PATH`, `FAMILY_MEMBERS`.

## Running Locally

```bash
uvicorn gregory.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000

## Debug Chat UI

A minimal static HTML chat interface for testing the API is in `debug/chat.html`. Serve it via HTTP to avoid CORS:

```bash
cd debug && python -m http.server 8080
```

Open http://localhost:8080/chat.html, set the API base URL and user ID, then send messages.
- Interactive docs: http://localhost:8000/docs

## Code Structure

```mermaid
flowchart TD
    main[main.py]
    config[config.py]
    store[store.py]
    ollama_ensure[ollama_ensure.py]

    api[api/]
    api_routes[api/routes/]
    api_schemas[api/schemas.py]

    ai[ai/]
    ai_config[ai/config.py]
    ai_router[ai/router.py]
    ai_selector[ai/selector.py]
    ai_prompts[ai/prompts.py]
    ai_observations[ai/observations.py]
    ai_providers[ai/providers/]

    notes[notes/]
    notes_service[notes/service.py]
    notes_loader[notes/loader.py]

    main --> api
    main --> config
    main --> ollama_ensure

    api --> api_routes
    api --> api_schemas

    api_routes --> health[health.py]
    api_routes --> users[users.py]
    api_routes --> chat[chat.py]

    chat --> ai
    chat --> notes
    chat --> store

    ai --> ai_config
    ai --> ai_router
    ai --> ai_selector
    ai --> ai_prompts
    ai --> ai_observations
    ai --> ai_providers

    ai_providers --> base[base.py]
    ai_providers --> ollama[ollama.py]
    ai_providers --> claude[claude.py]
    ai_providers --> gemini[gemini.py]
```

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `main.py` | FastAPI app, CORS, route mounting, lifespan (ollama_ensure) |
| `config.py` | Pydantic settings from config.json, .env, environment |
| `store.py` | In-memory conversation history per user |
| `ollama_ensure.py` | On startup: pull missing Ollama models when `ollama_ensure_models=true` |
| `api/routes/` | HTTP handlers: `health.py`, `users.py`, `chat.py` |
| `api/schemas.py` | Request/response Pydantic models |
| `ai/config.py` | Multi-provider config resolution (`ai_providers`, `model_priority`) |
| `ai/router.py` | Provider selection, `get_providers_for_message()`, fallback order |
| `ai/selector.py` | Model routing: ask priority model which AI handles each message |
| `ai/providers/` | `ollama.py`, `claude.py`, `gemini.py` — AI backend implementations |
| `ai/prompts.py` | System prompt construction, model selection prompt |
| `ai/observations.py` | Extract `[OBSERVATION: ...]` from responses and append to notes |
| `notes/service.py` | Read/write Markdown notes |
| `notes/loader.py` | Load notes as chat context |

## Testing

Dev dependencies include `pytest` and `pytest-asyncio`. Run:

```bash
pytest
```

**Note:** Test coverage is limited. See [ROADMAP.md](ROADMAP.md) for planned improvements. When adding features, add corresponding tests in a `tests/` directory at the project root.

## Adding a New AI Provider

1. Add a class in `ai/providers/` that extends `AIProvider` (see `base.py`).
2. Implement `async def generate(prompt, history, system_context) -> str`.
3. Update `ai/config.py` to support the new provider type in `AIProvidersConfig` and `_resolve_from_ai_config`.
4. Update `ai/router.py` to instantiate the new provider in `_instantiate()`.
5. Add corresponding settings in `config.py` and document in [CONFIGURATION.md](CONFIGURATION.md).

See [AI System](AI_SYSTEM.md) for the full provider and routing architecture.
