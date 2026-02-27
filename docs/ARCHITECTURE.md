# Architecture

## Overview

Gregory is an HTTP API layer that connects clients to AI backends (Ollama, Claude, Gemini), notes, and (future) integrations like Home Assistant and Jellyfin. It supports multi-provider configuration with model routing and automatic fallback.

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
    end

    clients --> FastAPI
    FastAPI --> Notes
    FastAPI --> Store
    FastAPI --> Router
    Router --> Config
    Router --> Selector
    Router --> Providers
    Providers --> OllamaServer
    Providers --> Anthropic
    Providers --> Gemini
    Notes --> NotesVolume
```

## Request Flow: Chat

The chat flow loads notes, optionally consults the model selector for routing, then tries providers in order until one succeeds.

```mermaid
sequenceDiagram
    participant Client
    participant ChatRoute
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

    subgraph root [Root]
        main[main.py]
        config[config.py]
        store[store.py]
        ollama_ensure[ollama_ensure.py]
    end

    main --> routes
    chat --> router
    chat --> notes
    chat --> store
    router --> config_ai
    router --> selector
    router --> providers
    main --> ollama_ensure
    notes --> config
    ai --> config
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

## Project Structure

```mermaid
flowchart TD
    root[gregory/]
    docker[docker/]
    src[src/gregory/]
    notes[notes/]
    debug[debug/]

    root --> docker
    root --> src
    root --> notes
    root --> debug

    docker --> Dockerfile[Dockerfile]
    docker --> compose[docker-compose.yml]

    src --> main[main.py]
    src --> config[config.py]
    src --> store[store.py]
    src --> ollama_ensure[ollama_ensure.py]
    src --> api[api/]
    src --> ai[ai/]
    src --> notes_src[notes/]

    api --> routes[api/routes/]
    api --> schemas[api/schemas.py]
    routes --> health[health.py]
    routes --> users[users.py]
    routes --> chat[chat.py]

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
```
