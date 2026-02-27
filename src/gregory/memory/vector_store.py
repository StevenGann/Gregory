"""Vector store for memory retrieval using ChromaDB."""

import asyncio
import logging
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from gregory.config import get_settings

logger = logging.getLogger(__name__)


class MemoryVectorStore:
    """ChromaDB-backed vector store for journal entries.

    ChromaDB is synchronous. All public async methods wrap synchronous ChromaDB
    calls in asyncio.run_in_executor so they do not block the event loop.

    Collection schema:
        id:        unique string per entry (e.g. "2026-01-15::1706123456789")
        document:  raw text of the journal entry or compressed summary
        metadata:  {date: "YYYY-MM-DD", user_id: str, type: "entry"|"summary"|"compressed"}
    """

    COLLECTION_NAME = "gregory_memory"

    def __init__(self, memory_path: Path | None = None) -> None:
        path = memory_path or get_settings().memory_path
        self._chroma_path = Path(path) / "chroma"
        self._client = None
        self._collection = None

    # --- Synchronous internals (called from executor threads) ---

    def _ensure_client(self) -> None:
        """Initialize ChromaDB client and collection. Called from executor thread."""
        if self._client is not None:
            return
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self._chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._chroma_path))

            settings = get_settings()
            if (
                settings.memory_embedding_provider == "ollama"
                and settings.ollama_base_url
            ):
                ef = embedding_functions.OllamaEmbeddingFunction(
                    url=settings.ollama_base_url,
                    model_name=settings.memory_embedding_model,
                )
                logger.info(
                    "[memory] Using Ollama embeddings: %s at %s",
                    settings.memory_embedding_model,
                    settings.ollama_base_url,
                )
            else:
                ef = embedding_functions.DefaultEmbeddingFunction()
                logger.info("[memory] Using default (onnxruntime) embeddings")

            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("[memory] ChromaDB initialized at %s", self._chroma_path)
        except ImportError:
            logger.error("[memory] chromadb not installed; memory search unavailable")
            raise
        except Exception as e:
            logger.error("[memory] Failed to initialize ChromaDB: %s", e)
            raise

    def _sync_index_entry(
        self,
        doc_id: str,
        text: str,
        entry_date: date,
        user_id: str = "",
        entry_type: str = "entry",
    ) -> None:
        self._ensure_client()
        if not text.strip():
            return
        metadata: dict[str, Any] = {
            "date": entry_date.isoformat(),
            "user_id": user_id,
            "type": entry_type,
        }
        self._collection.upsert(
            ids=[doc_id],
            documents=[text.strip()],
            metadatas=[metadata],
        )
        logger.debug("[memory] Indexed entry %s", doc_id)

    def _sync_search(
        self,
        query: str,
        n_results: int,
        threshold: float,
    ) -> list[dict[str, Any]]:
        self._ensure_client()
        if not query.strip():
            return []
        count = self._collection.count()
        if count == 0:
            return []
        actual_n = min(n_results, count)
        results = self._collection.query(
            query_texts=[query],
            n_results=actual_n,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict[str, Any]] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            # ChromaDB cosine distance: 0 = identical. Convert to similarity.
            similarity = 1.0 - dist
            if similarity >= threshold:
                hits.append({"text": doc, "metadata": meta, "similarity": similarity})
        return hits

    def _sync_delete_entries_for_month(self, year: int, month: int) -> None:
        self._ensure_client()
        prefix = f"{year:04d}-{month:02d}-"
        try:
            # Fetch all entries with their metadata, then filter by date prefix in Python.
            # ChromaDB's compound where-filter support varies across versions, so we avoid
            # relying on range operators and do the filtering ourselves.
            existing = self._collection.get(include=["metadatas"])
            ids_to_delete = [
                id_
                for id_, meta in zip(
                    existing.get("ids", []), existing.get("metadatas", [])
                )
                if (meta or {}).get("date", "").startswith(prefix)
            ]
            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
                logger.info(
                    "[memory] Deleted %d entries for %04d-%02d",
                    len(ids_to_delete),
                    year,
                    month,
                )
        except Exception as e:
            logger.warning("[memory] Failed to delete entries for %04d-%02d: %s", year, month, e)

    def _sync_index_journal_file(self, journal_date: date, content: str) -> None:
        """Bulk-index all bullet entries from a daily journal file."""
        self._ensure_client()
        lines = [
            ln.strip()
            for ln in content.splitlines()
            if ln.strip().startswith("- [")
        ]
        for i, line in enumerate(lines):
            doc_id = f"{journal_date.isoformat()}::bulk::{i}"
            metadata: dict[str, Any] = {
                "date": journal_date.isoformat(),
                "user_id": "",
                "type": "entry",
            }
            self._collection.upsert(
                ids=[doc_id],
                documents=[line],
                metadatas=[metadata],
            )

    # --- Async public API ---

    async def index_entry(
        self,
        doc_id: str,
        text: str,
        entry_date: date,
        user_id: str = "",
        entry_type: str = "entry",
    ) -> None:
        loop = asyncio.get_event_loop()
        fn = partial(self._sync_index_entry, doc_id, text, entry_date, user_id, entry_type)
        try:
            await loop.run_in_executor(None, fn)
        except Exception as e:
            logger.warning("[memory] Failed to index entry %s: %s", doc_id, e)

    async def search(
        self,
        query: str,
        n_results: int | None = None,
        threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search memory. Returns list of {text, metadata, similarity}."""
        settings = get_settings()
        top_k = n_results if n_results is not None else settings.memory_top_k
        sim_threshold = (
            threshold if threshold is not None else settings.memory_similarity_threshold
        )
        loop = asyncio.get_event_loop()
        fn = partial(self._sync_search, query, top_k, sim_threshold)
        try:
            return await loop.run_in_executor(None, fn)
        except Exception as e:
            logger.warning("[memory] Search failed: %s", e)
            return []

    async def delete_entries_for_month(self, year: int, month: int) -> None:
        loop = asyncio.get_event_loop()
        fn = partial(self._sync_delete_entries_for_month, year, month)
        try:
            await loop.run_in_executor(None, fn)
        except Exception as e:
            logger.warning("[memory] Failed to delete month %04d-%02d: %s", year, month, e)

    async def index_compressed_month(
        self, year: int, month: int, summary_text: str
    ) -> None:
        """Index a compressed monthly summary as a single document."""
        doc_id = f"{year:04d}-{month:02d}::compressed"
        entry_date = date(year, month, 1)
        await self.index_entry(
            doc_id=doc_id,
            text=summary_text,
            entry_date=entry_date,
            user_id="",
            entry_type="compressed",
        )

    async def reindex_all(self, journal_service) -> None:
        """Rebuild the vector index from all existing journal files. Idempotent (upsert)."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._ensure_client)
        except Exception as e:
            logger.error("[memory] Cannot reindex, ChromaDB unavailable: %s", e)
            return

        dates = journal_service.list_journal_dates()
        logger.info("[memory] Reindexing %d daily journal files", len(dates))
        for d in dates:
            content = journal_service.read_date(d)
            if content.strip():
                fn = partial(self._sync_index_journal_file, d, content)
                try:
                    await loop.run_in_executor(None, fn)
                except Exception as e:
                    logger.warning("[memory] Failed to reindex %s: %s", d, e)

        # Also index any compressed monthly files
        for f in journal_service._base.iterdir():
            if f.is_file() and f.suffix == ".md" and len(f.stem) == 7:
                try:
                    year, month = int(f.stem[:4]), int(f.stem[5:7])
                    content = f.read_text(encoding="utf-8")
                    if content.strip():
                        doc_id = f"{year:04d}-{month:02d}::compressed"
                        entry_date = date(year, month, 1)
                        fn = partial(
                            self._sync_index_entry,
                            doc_id,
                            content,
                            entry_date,
                            "",
                            "compressed",
                        )
                        await loop.run_in_executor(None, fn)
                except Exception as e:
                    logger.warning("[memory] Failed to reindex compressed %s: %s", f.name, e)

        logger.info("[memory] Reindex complete")
