# API Reference

Gregory exposes an HTTP API for chat, user management, and health checks. Interactive documentation (Swagger UI) is available at `/docs` when the server is running.

## Base URL

- Local: `http://localhost:8000`
- Docker: `http://localhost:8000` (or your host)

## API Overview

```mermaid
flowchart TB
    subgraph endpoints [Endpoints]
        Root["GET /"]
        Health["GET /health"]
        Users["GET /users"]
        Chat["POST /users/{user_id}/chat"]
    end

    subgraph responses [Typical Responses]
        Root --> RootResp[Service info + links]
        Health --> HealthResp[Status + ai_provider]
        Users --> UsersResp[user IDs array]
        Chat --> ChatResp[response + conversation_id]
    end
```

## Endpoints

### Root

**GET /**

Returns service info and links.

**Response:**
```json
{
  "name": "Gregory",
  "description": "Smart House AI",
  "docs": "/docs",
  "health": "/health"
}
```

---

### Health Check

**GET /health**

Health check for Docker, load balancers, and monitoring. Indicates which AI provider is primary (first in the configured order).

**Response:**
```json
{
  "status": "ok",
  "ollama_configured": true,
  "ai_provider": "ollama"
}
```

| Field | Type | Description |
|-------|------|-------------|
| status | string | Always `"ok"` when healthy |
| ollama_configured | boolean | `true` if `OLLAMA_BASE_URL` is set (legacy) or an Ollama endpoint exists in `ai_providers` |
| ai_provider | string \| null | Primary provider: `claude`, `gemini`, or `ollama`; `null` if none configured |

**Note:** When using `ai_providers` and `model_priority`, multiple providers may be configured. The `ai_provider` field reflects the *primary* (first) provider in the resolved order. See [AI System](AI_SYSTEM.md) for model routing and fallback behavior.

---

### List Users

**GET /users**

Returns the list of known family members. Combines `FAMILY_MEMBERS` from config and user IDs from the notes directory.

**Response:**
```json
{
  "users": ["alice", "bob", "kids"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| users | string[] | Sorted list of user IDs |

---

### Chat

**POST /users/{user_id}/chat**

Send a message as the specified user and receive Gregory's response. Each user has a single unified conversation history.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| user_id | string | Family member identifier (lowercase, alphanumeric + `-` and `_`) |

**Request Body:**
```json
{
  "message": "Hello Gregory!"
}
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| message | string | 1–16384 chars | The user's message |

**Response:**
```json
{
  "response": "Hello Alice! How can I help you today?",
  "conversation_id": "conv_1"
}
```

| Field | Type | Description |
|-------|------|-------------|
| response | string | Gregory's reply |
| conversation_id | string | Stable ID for this user's conversation |

**Error Responses:**

| Status | Condition |
|--------|-----------|
| 400 | Invalid `user_id` |
| 502 | AI provider error |
| 503 | No AI provider configured (e.g. `OLLAMA_BASE_URL` not set) |

---

## Chat Request Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Chat API
    participant NL as Notes Loader
    participant S as Store
    participant R as Router
    participant P as AI Provider

    C->>API: POST /users/{user_id}/chat
    API->>R: get_providers_for_message(message)
    Note over R: Optional: model selector reorders providers
    R-->>API: ordered providers
    API->>NL: load_notes_for_chat(user_id)
    NL-->>API: notes context
    API->>S: get_history(user_id)
    S-->>API: conversation history
    loop Try providers until success
        API->>P: generate(prompt, history, system_prompt)
        alt Success
            P-->>API: response text
        else Failure
            P-->>API: error (try next provider)
        end
    end
    API->>API: extract observations (if enabled)
    API->>S: append to history
    API-->>C: ChatResponse
```
