# Troubleshooting

Common issues and solutions when running Gregory.

## Config: ai_providers vs legacy

**Symptom:** You have `ai_providers` in `config.json` but Gregory seems to use legacy `OLLAMA_BASE_URL` or ignores some models.

**Cause:** When `ai_providers` is set and contains at least one provider, it **replaces** the legacy flat config. Legacy variables (`OLLAMA_BASE_URL`, `ANTHROPIC_API_KEY`, etc.) are only used when `ai_providers` is absent or empty.

**Fix:** Ensure `ai_providers` includes all endpoints you want. Use `model_priority` to control the order. For API keys, use `api_key_env` (e.g. `"api_key_env": "ANTHROPIC_API_KEY"`) instead of hardcoding in config.

---

## Model routing selects wrong model

**Symptom:** Model routing is enabled but Gregory always uses the same model, or picks an unexpected one.

**Causes and fixes:**

1. **Only one provider** — With a single model, the selector is skipped; that model is always used.
2. **Priority model fails** — If the selection call fails, Gregory falls back to config order. Check logs for `[model_select] Selection failed`.
3. **Parse failure** — The selector parses the priority model's response for a model ID. If parsing fails, config order is used. Set `LOG_LEVEL=DEBUG` and look for `[model_select] Could not parse model from response`.
4. **Disable routing** — Set `model_routing_enabled=false` to always use `model_priority` order without consulting the selector.

---

## Claude or Gemini not selected

**Symptom:** You set `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` but Gregory uses Ollama (or vice versa).

**Cause:** Provider priority is Claude > Gemini > Ollama when `AI_PROVIDER` is unset. If multiple are configured, the first in that order wins.

**Fix:** Set `AI_PROVIDER=claude`, `AI_PROVIDER=gemini`, or `AI_PROVIDER=ollama` to force a specific provider.

---

## 503: No AI provider configured

**Symptom:** `POST /users/{id}/chat` returns 503 with "No AI provider configured. Set OLLAMA_BASE_URL."

**Cause:** `OLLAMA_BASE_URL` is not set or is empty.

**Fix:**

- **Local:** Set `OLLAMA_BASE_URL=http://localhost:11434` in `.env` or `config.json`, or export it.
- **Docker:** In `.env` or `docker-compose.yml`, use `OLLAMA_BASE_URL=http://host.docker.internal:11434` (Docker Desktop) or the LAN IP of your Ollama host, e.g. `http://192.168.1.100:11434`.

Ensure Ollama is running and reachable from the Gregory container or host.

---

## 502: AI provider error

**Symptom:** Chat returns 502 with "AI provider error."

**Causes and fixes:**

1. **Ollama not running** — Start Ollama: `ollama serve` (or via your system service).
2. **Wrong URL** — Verify `OLLAMA_BASE_URL` points to the correct host and port.
3. **Network/firewall** — From Docker, `localhost` refers to the container, not the host. Use `host.docker.internal` (Docker Desktop) or the host's LAN IP.
4. **Model missing** — Ensure your `OLLAMA_MODEL` (default `llama3.2`) is pulled: `ollama pull llama3.2`.

---

## Claude or Gemini API errors

**Symptom:** 502 with "AI provider error" when using Claude or Gemini.

**Causes and fixes:**

1. **Invalid API key** — Verify `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` is correct and has not expired. Get keys from [console.anthropic.com](https://console.anthropic.com) or [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. **Rate limits** — Claude and Gemini have usage limits; check your account status.
3. **Model name** — Ensure `CLAUDE_MODEL` or `GEMINI_MODEL` matches a valid model identifier (e.g. `claude-3-5-sonnet-20241022`, `gemini-1.5-flash`).

---

## Notes not loading

**Symptom:** Gregory responds without notes context, or `/users` returns an unexpected list.

**Causes and fixes:**

1. **Wrong `NOTES_PATH`** — Default is `/app/notes` (Docker). For local dev, use `./notes` or an absolute path.
2. **Volume not mounted** — In Docker, ensure a volume or bind mount is set: `./notes:/app/notes`.
3. **File names** — User notes must be `{user_id}.md` (e.g. `alice.md`). Household notes: `household.md`.
4. **Permissions** — Gregory must be able to read the notes directory and files.

---

## Debug Chat UI: CORS or connection errors

**Symptom:** Opening `debug/chat.html` directly (file://) causes CORS or fetch errors when calling the API.

**Cause:** Browsers restrict cross-origin requests from `file://`.

**Fix:** Serve the debug UI over HTTP:

```bash
cd debug && python -m http.server 8080
```

Then open http://localhost:8080/chat.html. Set the API base URL to `http://localhost:8000` (or your Gregory URL).

---

## Docker: Cannot connect to Ollama on host

**Symptom:** Gregory in Docker cannot reach Ollama on the host.

**Fixes:**

- **Docker Desktop (Windows/macOS):** Use `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
- **Linux:** Use the host's LAN IP, e.g. `http://192.168.1.100:11434`, or run Ollama in a container on the same network.

---

## Config not loading

**Symptom:** Settings seem wrong; `config.json` or `.env` changes have no effect.

**Causes and fixes:**

1. **Precedence** — Environment variables override `.env`, which overrides `config.json`. Check for conflicting values.
2. **Path** — `config.json` is loaded from the working directory by default. Use `CONFIG_FILE` to specify another path.
3. **Docker** — Inside Docker, `.env` in the project root is typically loaded by Compose. `config.json` may not be present in the image unless copied.

---

## Logs

Set `LOG_LEVEL=DEBUG` for more detail:

```bash
LOG_LEVEL=DEBUG uvicorn gregory.main:app --reload --host 0.0.0.0 --port 8000
```

Or in `.env` / `config.json`:

```
LOG_LEVEL=DEBUG
```
