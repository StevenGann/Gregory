# Architecture

## Overview

Gregory is an HTTP API layer that connects clients to AI backends, notes, and (future) integrations like Home Assistant and Jellyfin.

```mermaid
flowchart TB
    subgraph clients [Clients]
        WebApp[Web / Mobile App]
        VoiceInterface[Voice Interface]
        OtherApps[Other Apps]
    end

    subgraph gregory [Gregory]
        subgraph api [API Layer]
            FastAPI[FastAPI Server]
        end
        subgraph core [Core]
            Notes[Notes Service]
            Store[Conversation Store]
        end
        subgraph ai [AI]
            Router[Provider Router]
            Ollama[Ollama Provider]
        end
    end

    subgraph external [External]
        OllamaServer[Ollama Server]
        NotesVolume[Notes Volume]
    end

    clients --> FastAPI
    FastAPI --> Notes
    FastAPI --> Store
    FastAPI --> Router
    Router --> Ollama
    Ollama --> OllamaServer
    Notes --> NotesVolume
```

## Request Flow: Chat

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant ChatRoute
    participant NotesLoader
    participant Store
    participant Router
    participant Ollama

    Client->>FastAPI: POST /users/alice/chat
    FastAPI->>ChatRoute: chat(alice, message)
    ChatRoute->>NotesLoader: load_notes_for_chat(alice)
    NotesLoader->>NotesLoader: read household.md + alice.md
    NotesLoader-->>ChatRoute: notes_context
    ChatRoute->>Store: get_history(alice)
    Store-->>ChatRoute: history
    ChatRoute->>Router: get_provider()
    Router-->>ChatRoute: OllamaProvider
    ChatRoute->>Ollama: generate(prompt, history, system_context)
    Ollama->>Ollama: POST /api/chat
    Ollama-->>ChatRoute: response_text
    ChatRoute->>Store: append(user, user, message)
    ChatRoute->>Store: append(user, assistant, response)
    ChatRoute-->>Client: ChatResponse
```

## Component Diagram

```mermaid
flowchart LR
    subgraph api [api/]
        health[health.py]
        users[users.py]
        chat[chat.py]
        schemas[schemas.py]
    end

    subgraph ai [ai/]
        router[router.py]
        prompts[prompts.py]
        providers[providers/]
    end

    subgraph notes [notes/]
        service[service.py]
        loader[loader.py]
    end

    subgraph shared [shared]
        config[config.py]
        store[store.py]
    end

    chat --> config
    chat --> notes
    chat --> ai
    chat --> store
    users --> notes
    users --> config
    notes --> config
    ai --> config
```

## Data Flow: Notes

```mermaid
flowchart LR
    subgraph input [Input]
        Chat[Chat Message]
        Observations[AI Observations - planned]
    end

    subgraph notes_dir [notes/]
        household[household.md]
        alice[alice.md]
        bob[bob.md]
    end

    subgraph usage [Usage]
        SystemPrompt[System Prompt]
    end

    household --> NotesLoader
    alice --> NotesLoader
    bob --> NotesLoader
    NotesLoader --> SystemPrompt
    SystemPrompt --> AIProvider
    Chat --> AIProvider
    AIProvider --> Observations
    Observations -.-> notes_dir
```

**Note:** The dotted line from AI to notes represents **planned** functionality: Gregory will eventually be able to append observations to notes as he learns. This is not yet implemented. See [ROADMAP.md](ROADMAP.md).

## Project Structure

```mermaid
flowchart TD
    root[gregory/]
    docker[docker/]
    src[src/gregory/]
    notes[notes/]

    root --> docker
    root --> src
    root --> notes

    docker --> Dockerfile[Dockerfile]
    docker --> compose[docker-compose.yml]

    src --> main[main.py]
    src --> config[config.py]
    src --> store[store.py]
    src --> api[api/]
    src --> ai[ai/]
    src --> notes_src[notes/]

    api --> health[health.py]
    api --> users[users.py]
    api --> chat[chat.py]
    api --> schemas[schemas.py]

    ai --> router[router.py]
    ai --> prompts[prompts.py]
    ai --> providers[providers/]

    providers --> base[base.py]
    providers --> ollama[ollama.py]

    notes_src --> service[service.py]
    notes_src --> loader[loader.py]
```
