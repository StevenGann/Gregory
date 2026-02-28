# Roadmap

Gregory is in active development. This document outlines planned features and integration priorities.

## Phase 1 (Current)

- [x] HTTP API with FastAPI
- [x] Chat endpoint with per-user history
- [x] Ollama as AI backend
- [x] Notes system (household + per-user Markdown)
- [x] Docker and Raspberry Pi deployment
- [x] Debug Chat UI

## Phase 2: AI & Notes

- [x] **AI provider expansion** — Add Claude and Gemini as optional backends
- [x] **Notes observations** — Gregory writes observations back to notes as he learns (enable with `OBSERVATIONS_ENABLED=true`; see [ARCHITECTURE.md](ARCHITECTURE.md#data-flow-notes))
- [x] **Configurable model** — Allow choosing the Ollama model (e.g. `llama3.2`, `mistral`) via `OLLAMA_MODEL`
- [x] **Multi-provider config** — `ai_providers` and `model_priority` for cost control and multiple Ollama/Claude/Gemini endpoints
- [x] **Model routing** — Highest-priority model selects which AI handles each message (see [AI_SYSTEM.md](AI_SYSTEM.md))
- [x] **Provider fallback** — Automatic fallback to next provider when one fails
- [x] **Ollama ensure** — On startup, pull missing Ollama models when `ollama_ensure_models=true`

## Phase 3: Integrations

- [x] **Home Assistant** — Control lights, thermostats, and devices via natural language (see [HOME_ASSISTANT.md](HOME_ASSISTANT.md))
- [ ] **Jellyfin** — Query media library, start playback, manage content
- [ ] **Webhooks / triggers** — Allow external systems to trigger Gregory actions

## Phase 4: Clients

- [ ] **Web app** — Persistent web interface (beyond debug chat)
- [ ] **Voice interface** — Speech-to-text and text-to-speech integration

## Contributing

If you’d like to work on any of these items, see [CONTRIBUTING.md](../CONTRIBUTING.md) and open an issue to discuss.
