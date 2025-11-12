from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import chromadb
from chromadb import Collection
from sentence_transformers import SentenceTransformer

from ehs_ai.config import Settings, get_settings
from ehs_ai.utils.logger import get_logger

logger = get_logger(__name__)


class VectorMemory:
    """Thin wrapper around ChromaDB for storing and retrieving safety policies."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = chromadb.PersistentClient(path=str(self._settings.vector_db_path))
        self._collection: Collection = self._client.get_or_create_collection(
            name=self._settings.vector_collection
        )
        self._embedder = SentenceTransformer(self._settings.embedding_model_name)

    def upsert(self, *, documents: Iterable[dict]) -> None:
        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[dict] = []
        for item in documents:
            doc_id = item.get("id")
            text = item.get("text")
            metadata = item.get("metadata", {})
            if not doc_id or not text:
                continue
            ids.append(str(doc_id))
            texts.append(str(text))
            metadatas.append(metadata)
        if not ids:
            return
        logger.info("Upserting %s policy documents into vector memory.", len(ids))
        embeddings = self._embedder.encode(texts, show_progress_bar=False).tolist()
        self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)

    def query(self, *, text: str, n_results: int = 3) -> List[dict]:
        if not text:
            return []
        embedding = self._embedder.encode([text], show_progress_bar=False)
        results = self._collection.query(query_embeddings=embedding, n_results=n_results)
        if not results["ids"]:
            return []
        matches: List[dict] = []
        for doc_id, document, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            matches.append(
                {
                    "id": doc_id,
                    "document": document,
                    "metadata": metadata,
                    "distance": distance,
                }
            )
        return matches

    def ensure_seed_documents(self, *, directory: Path | None = None) -> None:
        """Load sample policies if the collection is empty."""
        if self._collection.count() > 0:
            return
        docs: List[dict] = []
        source_dir = directory or Path("./storage/policies")
        if source_dir.exists():
            for path in source_dir.glob("*.txt"):
                text = path.read_text(encoding="utf-8")
                docs.append(
                    {
                        "id": path.stem,
                        "text": text,
                        "metadata": {"source": str(path), "tag": "policy"},
                    }
                )
        if not docs:
            logger.info("Using built-in seed policies for vector memory.")
            docs = [
                {
                    "id": "ppe_policy",
                    "text": (
                        "All personnel in production areas must wear ANSI Z89.1 hard hats, "
                        "ANSI Z87.1 eye protection, and high-visibility vests at all times."
                    ),
                    "metadata": {"source": "seed", "tag": "PPE"},
                },
                {
                    "id": "lockout_tagout",
                    "text": (
                        "Before servicing equipment, apply lockout/tagout per OSHA 1910.147. "
                        "Verify zero energy state prior to maintenance activities."
                    ),
                    "metadata": {"source": "seed", "tag": "LOTO"},
                },
                {
                    "id": "chemical_handling",
                    "text": (
                        "When handling corrosive chemicals, use splash-resistant gloves, "
                        "face shields, and ensure eyewash stations are operational within "
                        "10 seconds travel time."
                    ),
                    "metadata": {"source": "seed", "tag": "Chemical"},
                },
            ]
        self.upsert(documents=docs)

