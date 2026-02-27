# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Home Assistant integration
- Jellyfin integration

## [0.2.0] - 2025-02

### Added

- **Claude (Anthropic) provider** — Set `ANTHROPIC_API_KEY` and optionally `AI_PROVIDER=claude`
- **Gemini (Google) provider** — Set `GEMINI_API_KEY` and optionally `AI_PROVIDER=gemini`
- **Configurable Ollama model** — `OLLAMA_MODEL` (default: `llama3.2`)
- **Notes observations** — When `OBSERVATIONS_ENABLED=true`, Gregory appends learned facts using `[OBSERVATION: ...]` in responses
- **Provider selection** — `AI_PROVIDER` to prefer claude, gemini, or ollama; otherwise first available wins
- **Health endpoint** — Now returns `ai_provider` indicating active backend

## [0.1.0] - 2025-02

### Added

- Initial release
- HTTP API with FastAPI
- Chat endpoint: `POST /users/{user_id}/chat`
- Health check: `GET /health`
- User list: `GET /users`
- Ollama as AI backend
- Notes system: `household.md` and per-user Markdown files
- In-memory conversation history per user
- Docker and docker-compose support
- Raspberry Pi ARM64 build support
- Debug Chat UI (`debug/chat.html`)
- Configuration via `config.json`, `.env`, and environment variables
