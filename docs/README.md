# Gregory Documentation

Documentation for Gregory, the Smart House AI.

## Documentation Index

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE.md) | System design, components, and data flow |
| [AI System](AI_SYSTEM.md) | Model routing, provider selection, and fallback |
| [API Reference](API.md) | Detailed HTTP API specification |
| [Configuration](CONFIGURATION.md) | Environment variables and settings |
| [Development](DEVELOPMENT.md) | Local setup, testing, and code structure |
| [Deployment](DEPLOYMENT.md) | Docker, Raspberry Pi, and production deployment |
| [Troubleshooting](TROUBLESHOOTING.md) | Common issues and solutions |
| [Roadmap](ROADMAP.md) | Planned features and integrations |

## Concepts at a Glance

```mermaid
flowchart LR
    subgraph inputs [Inputs]
        Client[Client]
        Notes[Notes]
    end

    subgraph gregory [Gregory]
        API[API]
        Router[Router]
        Selector[Selector]
        Providers[Providers]
    end

    subgraph external [External]
        Ollama[Ollama]
        Claude[Claude]
        Gemini[Gemini]
    end

    Client --> API
    API --> Notes
    API --> Router
    Router --> Selector
    Router --> Providers
    Providers --> Ollama
    Providers --> Claude
    Providers --> Gemini
```

## Quick Links

- **Debug Chat UI**: `debug/chat.html` — Static HTML interface for testing. Serve with `python -m http.server 8080` from the `debug/` directory.
