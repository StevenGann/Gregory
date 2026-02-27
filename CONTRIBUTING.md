# Contributing to Gregory

Thank you for your interest in contributing to Gregory! This document explains how to get set up and submit changes.

## Development Setup

1. Clone the repository and create a virtual environment:

   ```bash
   git clone https://github.com/your-org/gregory.git
   cd gregory
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

2. Install in editable mode with dev dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

3. Copy configuration files and configure:

   ```bash
   cp .env.example .env
   # Edit .env with OLLAMA_BASE_URL, FAMILY_MEMBERS, etc.
   ```

4. Run the server:

   ```bash
   uvicorn gregory.main:app --reload --host 0.0.0.0 --port 8000
   ```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for full details.

## Code Style

- Use Python 3.11+ features.
- Follow existing patterns in the codebase.
- Add docstrings to new modules, classes, and public functions.
- Use type hints where applicable.

## Project Structure

| Path | Purpose |
|------|---------|
| `src/gregory/` | Main application code |
| `src/gregory/api/routes/` | HTTP route handlers |
| `src/gregory/ai/providers/` | AI backend implementations |
| `src/gregory/notes/` | Notes loading and service |
| `docs/` | Documentation |
| `debug/` | Debug and testing utilities |

## Adding a New AI Provider

1. Create a new file in `ai/providers/` extending `AIProvider` (see `base.py`).
2. Implement `async def generate(prompt, history, system_context) -> str`.
3. Update `ai/router.py` to return the new provider based on config.
4. Add corresponding settings in `config.py` and document in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#adding-a-new-ai-provider) and [docs/AI_SYSTEM.md](docs/AI_SYSTEM.md) for the full guide.

## Pull Requests

1. Create a branch from `main`.
2. Make your changes and ensure the server runs.
3. Run tests: `pytest` (when tests exist).
4. Update documentation if needed.
5. Submit a PR with a clear description of the change.

## Documentation

- Update [docs/](docs/) when adding features or changing behavior.
- Add entries to [CHANGELOG.md](CHANGELOG.md) for user-facing changes.
- Keep the [README](README.md) overview accurate.

## Questions?

Open an issue for questions, bugs, or feature requests.
