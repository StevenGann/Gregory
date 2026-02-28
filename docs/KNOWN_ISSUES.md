# Known Issues

This document lists known limitations and issues in Gregory. For troubleshooting common problems, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Config Reload

**Description:** Settings are loaded once at startup. Changes to `config.json`, `.env`, or environment variables generally require a server restart to take effect.

**Mitigation:** The debug API (`PATCH /debug/config`) writes directly to `config.json` and calls `get_settings.cache_clear()`, so config changes made via the debug UI take effect for the next request. However, some settings (e.g. `ai_providers`, `memory_enabled`) may require a full restart for proper initialization (e.g. memory reindex, heartbeat tasks).

---

## Conversation Persistence

**Description:** [store.py](../src/gregory/store.py) uses in-memory conversation history. Chat history is lost when the server restarts.

**Mitigation:** Documented as a current limitation. Persistence (e.g. to disk or a database) is a candidate for a future ROADMAP item.

---

## Test Coverage

**Description:** Test coverage is limited per [DEVELOPMENT.md](DEVELOPMENT.md). Not all modules have corresponding tests.

**Mitigation:** Add tests incrementally when adding or modifying features. See `tests/` for existing test structure.

---

## Config Security

**Description:** `config.json` may contain API keys and secrets. Committing real keys to version control is a security risk.

**Mitigation:**
- Prefer `.env` for API keys and keep `.env` in `.gitignore`
- Use `api_key_env` in `ai_providers` to reference environment variables instead of hardcoding keys
- Ensure `config.json.example` uses placeholders (`null` or `"your-key-here"`) and never real credentials

---

## Docker Config

**Description:** When running in Docker, `config.json` may not be present in the image. Docker deployments typically rely on `.env` or environment variables passed via `docker-compose.yml`.

**Mitigation:** Document using `.env` or environment variables in Docker. If you need `config.json` in Docker, copy it into the image via the Dockerfile or mount it as a volume.
