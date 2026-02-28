# Implementation Status

Current status of Gregory features. See [ROADMAP.md](ROADMAP.md) for planned work.

## Implemented

```mermaid
flowchart TB
    subgraph implemented [Implemented]
        HTTP[HTTP API]
        Chat[Chat endpoint]
        Users[Users endpoint]
        Health[Health check]
        MemoryAPI[Memory search API]
        DebugAPI[Debug API: logs, config]
        Notes[Notes system]
        Obs[Observations]
        MultiProvider[Multi-provider AI]
        ModelRouting[Model routing]
        Fallback[Provider fallback]
        OllamaEnsure[Ollama ensure]
        Memory[Memory: journal, vector, compression]
        Heartbeat[Heartbeat: reflection, cleanup, summary]
        HA[Home Assistant]
        Wiki[Wikipedia search]
        WebSearch[Web search]
        FactCheck[Fact-check strict]
    end
```

| Category | Features |
|----------|----------|
| **API** | HTTP API, chat, users, health, memory search, debug (logs, config) |
| **Notes** | Household, per-user, Gregory, entities, services; observations |
| **AI** | Multi-provider (Ollama, Claude, Gemini), model routing, fallback, Ollama ensure |
| **Memory** | Journal, ChromaDB vector store, daily summary, monthly compression |
| **Heartbeat** | Self-reflection, notes cleanup, daily summary, memory compression |
| **Tools** | Home Assistant, Wikipedia, Web Search, fact-check strict |

## Not Implemented

| Feature | Notes |
|---------|-------|
| **Jellyfin** | Media library, playback control |
| **Webhooks / triggers** | External systems triggering Gregory |
| **Persistent web app** | Beyond debug chat UI |
| **Voice interface** | Speech-to-text, text-to-speech |
| **Conversation persistence** | Chat history lost on restart |
