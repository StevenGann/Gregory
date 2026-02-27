# Architecture

## Overview

Gregory is an HTTP API layer that connects clients to AI backends (Ollama, Claude, Gemini), notes, and (future) integrations like Home Assistant and Jellyfin. It supports multi-provider configuration with model routing and automatic fallback. An optional memory system provides persistent journal storage and semantic retrieval.

```mermaid
flowchart TB
    subgraph clients [Clients]
        WebApp[Web / Mobile App]
        VoiceInterface[Voice Interface]
        DebugUI[Debug Chat UI]
    end

    subgraph gregory [Gregory]
        subgraph api [API Layer]
            FastAPI[FastAPI Server]
        end
        subgraph core [Core]
            Notes[Notes Service]
            Store[Conversation Store]
            Memory[Memory Service]
        end
        subgraph ai [AI Subsystem]
            Config[AI Config]
            Router[Provider Router]
            Selector[Model Selector]
            Providers[Providers]
        end
    end

    subgraph external [External]
        OllamaServer[Ollama Server]
        Anthropic[Anthropic API]
        Gemini[Gemini API]
        NotesVolume[Notes Volume]
        MemoryVolume[Memory Volume]
        ChromaDB[(ChromaDB)]
    end

    clients --> FastAPI
    FastAPI --> Notes
    FastAPI --> Store
    FastAPI --> Memory
    FastAPI --> Router
    Router --> Config
    Router --> Selector
    Router --> Providers
    Providers --> OllamaServer
    Providers --> Anthropic
    Providers --> Gemini
    Notes --> NotesVolume
    Memory --> MemoryVolume
    Memory --> ChromaDB
```

## Request Flow: Chat

The chat flow loads notes and memory context, optionally consults the model selector for routing, then tries providers in order until one succeeds.

```mermaid
sequenceDiagram
    participant Client
    participant ChatRoute
    participant MemoryLoader
    participant NotesLoader
    participant Store
    participant Router
    participant Selector
    participant Provider1
    participant Provider2

    Client->>ChatRoute: POST /users/alice/chat
    ChatRoute->>Router: get_providers_for_message(message)
    alt model_routing_enabled
        Router->>Selector: select_model_for_message(message)
        Selector->>Provider1: (priority model) Which model for this?
        Provider1-->>Selector: chosen model
        Selector-->>Router: reordered provider list
    end
    Router-->>ChatRoute: ordered providers
    opt memory_enabled
        ChatRoute->>MemoryLoader: load_memory_for_chat(alice, message)
        MemoryLoader-->>ChatRoute: memory_context
    end
    ChatRoute->>NotesLoader: load_notes_for_chat(alice)
    NotesLoader-->>ChatRoute: notes_context
    ChatRoute->>Store: get_history(alice)
    Store-->>ChatRoute: history
    loop Try each provider until success
        ChatRoute->>Provider1: generate(...)
        alt Provider1 fails
            Provider1-->>ChatRoute: error
            ChatRoute->>Provider2: generate(...)
            Provider2-->>ChatRoute: response_text
        else Provider1 succeeds
            Provider1-->>ChatRoute: response_text
        end
    end
    ChatRoute->>ChatRoute: extract_observations (if enabled)
    opt memory_enabled
        ChatRoute->>ChatRoute: extract [JOURNAL:] / [MEMORY_SEARCH:] markers
        ChatRoute->>MemoryLoader: write entries + queue search results
    end
    ChatRoute->>Store: append(user, assistant, response)
    ChatRoute-->>Client: ChatResponse
```

## Model Routing Flow

When `model_routing_enabled=true`, the highest-priority model decides which AI handles each message. This reduces cost by steering simple tasks to local/free models.

```mermaid
flowchart LR
    subgraph input [Input]
        Message[User Message]
    end

    subgraph selector [Model Selector]
        Priority1[Priority 1 Model]
        Prompt[Selection Prompt]
        Parse[Parse Response]
    end

    subgraph output [Output]
        Reordered[Reordered Provider List]
    end

    Message --> Prompt
    Prompt --> Priority1
    Priority1 --> Parse
    Parse --> Reordered
```

## Component Diagram

```mermaid
flowchart TB
    subgraph api [api/]
        routes[api/routes/]
        schemas[api/schemas.py]
    end

    subgraph routes_detail [api/routes/]
        health[health.py]
        users[users.py]
        chat[chat.py]
        mem_route[memory.py]
    end

    subgraph ai [ai/]
        config_ai[ai/config.py]
        router[ai/router.py]
        selector[ai/selector.py]
        prompts[ai/prompts.py]
        observations[ai/observations.py]
        providers[ai/providers/]
    end

    subgraph notes [notes/]
        service[notes/service.py]
        loader[notes/loader.py]
    end

    subgraph memory [memory/]
        journal[memory/journal.py]
        vector_store[memory/vector_store.py]
        mem_service[memory/service.py]
        mem_loader[memory/loader.py]
    end

    subgraph root [Root]
        main[main.py]
        config[config.py]
        store[store.py]
        heartbeat[heartbeat.py]
        ollama_ensure[ollama_ensure.py]
    end

    main --> routes
    chat --> router
    chat --> notes
    chat --> store
    chat --> mem_loader
    chat --> observations
    mem_route --> vector_store
    mem_loader --> vector_store
    mem_service --> journal
    mem_service --> vector_store
    heartbeat --> mem_service
    router --> config_ai
    router --> selector
    router --> providers
    main --> ollama_ensure
    notes --> config
    ai --> config
    memory --> config
```

## Data Flow: Notes

```mermaid
flowchart LR
    subgraph input [Input]
        Chat[Chat Message]
        Observations[AI Observations]
    end

    subgraph notes_dir [notes/]
        household[household.md]
        gregory[gregory.md]
        entities[entities/*.md]
        alice[alice.md]
        bob[bob.md]
    end

    subgraph usage [Usage]
        SystemPrompt[System Prompt]
    end

    household --> NotesLoader
    gregory --> NotesLoader
    entities --> NotesLoader
    alice --> NotesLoader
    bob --> NotesLoader
    NotesLoader --> SystemPrompt
    SystemPrompt --> AIProvider
    Chat --> AIProvider
    AIProvider --> Observations
    Observations -.-> notes_dir
```

**Note:** The dotted line from AI to notes is implemented when `OBSERVATIONS_ENABLED=true`. Gregory extracts observation blocks and routes them: `[OBSERVATION: ...]` → user, `[GREGORY_NOTE: ...]` → gregory.md, `[HOUSEHOLD_NOTE: ...]` → household, `[NOTE:entity: ...]` → entities/. See [CONFIGURATION.md](CONFIGURATION.md).

## Data Flow: Memory

```mermaid
flowchart LR
    subgraph write [Writing]
        ChatMsg[Chat Message]
        JournalMarker["[JOURNAL: ...] in AI response"]
        JournalService[Journal Service]
        VectorStore[Vector Store]
    end

    subgraph memory_dir [memory/]
        DailyFile["YYYY-MM-DD.md"]
        MonthlyFile["YYYY-MM.md (compressed)"]
        ChromaDB[(ChromaDB)]
    end

    subgraph read [Reading]
        AutoSearch[Pre-chat auto-search]
        PendingSearch["[MEMORY_SEARCH: ...] results"]
        MemCtx[Memory Context]
        SystemPrompt[System Prompt]
    end

    subgraph heartbeat [Heartbeat]
        DailySummary[Daily Summary Task]
        Compression[Monthly Compression Task]
    end

    ChatMsg --> AutoSearch
    AutoSearch --> VectorStore
    VectorStore --> MemCtx
    PendingSearch --> MemCtx
    MemCtx --> SystemPrompt

    JournalMarker --> JournalService
    JournalService --> DailyFile
    JournalService --> VectorStore
    VectorStore --> ChromaDB

    DailySummary --> JournalService
    Compression --> JournalService
    Compression --> MonthlyFile
    MonthlyFile --> VectorStore
```

**Note:** The memory system is optional (`MEMORY_ENABLED=true`). It complements notes with temporal, event-driven entries written automatically during conversations. See [MEMORY.md](MEMORY.md) for full details.

## Project Structure

```mermaid
flowchart TD
    root[gregory/]
    docker[docker/]
    src[src/gregory/]
    notes[notes/]
    memory_dir[memory/]
    tests_dir[tests/]
    debug[debug/]

    root --> docker
    root --> src
    root --> notes
    root --> memory_dir
    root --> tests_dir
    root --> debug

    docker --> Dockerfile[Dockerfile]
    docker --> compose[docker-compose.yml]

    src --> main[main.py]
    src --> config[config.py]
    src --> store[store.py]
    src --> heartbeat[heartbeat.py]
    src --> ollama_ensure[ollama_ensure.py]
    src --> api[api/]
    src --> ai[ai/]
    src --> notes_src[notes/]
    src --> memory_src[memory/]

    api --> routes[api/routes/]
    api --> schemas[api/schemas.py]
    routes --> health[health.py]
    routes --> users[users.py]
    routes --> chat[chat.py]
    routes --> mem_route[memory.py]

    ai --> config_ai[ai/config.py]
    ai --> router[ai/router.py]
    ai --> selector[ai/selector.py]
    ai --> prompts[ai/prompts.py]
    ai --> observations[ai/observations.py]
    ai --> providers[ai/providers/]

    providers --> base[base.py]
    providers --> ollama[ollama.py]
    providers --> claude[claude.py]
    providers --> gemini[gemini.py]

    notes_src --> service[service.py]
    notes_src --> loader[loader.py]

    memory_src --> journal[journal.py]
    memory_src --> vector_store[vector_store.py]
    memory_src --> mem_service[service.py]
    memory_src --> mem_loader[loader.py]
```
