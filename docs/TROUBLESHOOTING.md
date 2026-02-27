# Troubleshooting

Common issues and solutions when running Gregory.

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
4. **Model missing** — Ensure the default model (`llama3.2`) is pulled: `ollama pull llama3.2`.

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
