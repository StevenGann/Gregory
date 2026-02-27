# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Claude and Gemini AI providers
- Notes observations (AI writing back to notes)
- Home Assistant integration
- Jellyfin integration

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
