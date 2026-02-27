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

- [ ] **AI provider expansion** — Add Claude and Gemini as optional backends
- [ ] **Notes observations** — Gregory writes observations back to notes as he learns (see [ARCHITECTURE.md](ARCHITECTURE.md#data-flow-notes))
- [ ] **Configurable model** — Allow choosing the Ollama model (e.g. `llama3.2`, `mistral`) via config

## Phase 3: Integrations

- [ ] **Home Assistant** — Control lights, thermostats, and devices via natural language
- [ ] **Jellyfin** — Query media library, start playback, manage content
- [ ] **Webhooks / triggers** — Allow external systems to trigger Gregory actions

## Phase 4: Clients

- [ ] **Web app** — Persistent web interface (beyond debug chat)
- [ ] **Voice interface** — Speech-to-text and text-to-speech integration

## Contributing

If you’d like to work on any of these items, see [CONTRIBUTING.md](../CONTRIBUTING.md) and open an issue to discuss.
