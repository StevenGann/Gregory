"""Shared fixtures for Gregory tests."""

# ---------------------------------------------------------------------------
# Pre-import mocks: prevent optional AI provider SDKs from causing import
# failures in environments where system packages (e.g. cryptography) may be
# broken or missing.
#
# We pre-populate sys.modules with MagicMock stubs for packages that are NOT
# yet imported. If they are already present in sys.modules (e.g. in a CI
# environment where all packages are properly installed), the real modules are
# left untouched.
# ---------------------------------------------------------------------------
import sys
from unittest.mock import MagicMock

for _mod in ("google.genai", "anthropic"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---------------------------------------------------------------------------

import hashlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fake embedding function: deterministic, distinct per text, no network calls
# ---------------------------------------------------------------------------

def _make_fake_ef():
    """
    Build a ChromaDB-compatible embedding function for tests.
    - Same text → same unit vector → cosine similarity 1.0 with itself
    - Different texts → different unit vectors (via sha256) → similarity ≈ 0
    - Dimension: 384 (matches all-MiniLM-L6-v2, accepted by ChromaDB)
    - No network calls, fully deterministic
    Implements the full EmbeddingFunction protocol required by ChromaDB 1.x.
    """
    from chromadb.utils.embedding_functions import EmbeddingFunction, register_embedding_function
    from chromadb.api.types import Documents, Embeddings
    from typing import Any, Dict

    DIM = 384

    @register_embedding_function
    class FakeEmbeddingFunction(EmbeddingFunction[Documents]):
        def __init__(self) -> None:
            pass

        @staticmethod
        def name() -> str:
            return "fake-test-ef"

        def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
            result = []
            for text in input:
                vec = [0.0] * DIM
                h = int(hashlib.sha256(str(text).encode()).hexdigest()[:8], 16)
                vec[h % DIM] = 1.0
                result.append(vec)
            return result

        def get_config(self) -> Dict[str, Any]:
            return {}

        @staticmethod
        def build_from_config(config: Dict[str, Any]) -> "FakeEmbeddingFunction":
            return FakeEmbeddingFunction()

    return FakeEmbeddingFunction()


# ---------------------------------------------------------------------------
# Settings override: prevent loading real config files or env vars
# ---------------------------------------------------------------------------

class _FakeSettings:
    """Minimal settings object for tests."""
    log_level = "INFO"
    notes_path = Path("/tmp/gregory-test-notes")
    memory_enabled = True
    memory_path = Path("/tmp/gregory-test-memory")
    memory_similarity_threshold = 0.7
    memory_top_k = 3
    memory_embedding_provider = "default"
    memory_embedding_model = "nomic-embed-text"
    ollama_base_url = None
    observations_enabled = True
    system_prompt = None
    family_members = "alice,bob"


@pytest.fixture()
def fake_settings(monkeypatch):
    """Monkeypatch get_settings() to return a predictable test settings object."""
    settings = _FakeSettings()
    monkeypatch.setattr("gregory.config.get_settings", lambda: settings)
    # Also patch in each module that calls it at import time
    for mod in [
        "gregory.memory.journal",
        "gregory.memory.vector_store",
        "gregory.memory.service",
        "gregory.memory.loader",
        "gregory.ai.prompts",
    ]:
        try:
            monkeypatch.setattr(f"{mod}.get_settings", lambda: settings)
        except AttributeError:
            pass
    return settings


# ---------------------------------------------------------------------------
# ChromaDB mock: use EphemeralClient + FakeEmbeddingFunction so no I/O or
# model downloads happen during tests.
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_chroma(monkeypatch):
    """
    Replace PersistentClient with EphemeralClient and embedding functions
    with a fake implementation so ChromaDB tests run offline and quickly.

    Note: chromadb.EphemeralClient shares a global in-memory backend across
    instances, so we patch COLLECTION_NAME with a unique value per test to
    ensure test isolation.
    """
    import uuid

    import chromadb
    from chromadb.utils import embedding_functions

    from gregory.memory import vector_store as vs_module

    fake_ef = _make_fake_ef()

    # Each test gets a fresh, unique collection name so shared EphemeralClient
    # state doesn't bleed between tests.
    unique_name = f"test_{uuid.uuid4().hex[:12]}"
    monkeypatch.setattr(vs_module.MemoryVectorStore, "COLLECTION_NAME", unique_name)

    monkeypatch.setattr(
        chromadb,
        "PersistentClient",
        lambda path, **kwargs: chromadb.EphemeralClient(),
    )
    monkeypatch.setattr(
        embedding_functions,
        "DefaultEmbeddingFunction",
        lambda: fake_ef,
    )
    monkeypatch.setattr(
        embedding_functions,
        "OllamaEmbeddingFunction",
        lambda url, model_name: fake_ef,
    )
    return fake_ef
