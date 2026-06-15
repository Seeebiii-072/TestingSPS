from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any

import chromadb

from ai.config.settings import get_settings
from ai.kb.chunker import TextChunk
from ai.kb.embedder import embed_texts


COLLECTION_NAME = "securedesk_knowledge_base"


@dataclass(frozen=True)
class StoredDocument:
    filename: str
    chunk_count: int
    created_at: datetime | None
    document_hash: str | None


@dataclass(frozen=True)
class VectorSearchResult:
    content: str
    distance: float
    metadata: dict[str, str | int | float | bool]


class VectorStore:
    def __init__(self, store_path: Path | None = None) -> None:
        configured_path = store_path or get_settings().kb_store_path
        configured_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(configured_path.resolve()))
        self._collection: Any = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._lock = RLock()

    def index_chunks(self, chunks: list[TextChunk]) -> int:
        if not chunks:
            return 0
        with self._lock:
            embeddings = embed_texts([chunk.content for chunk in chunks])
            self._collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=[chunk.content for chunk in chunks],
                embeddings=embeddings,
                metadatas=[chunk.metadata() for chunk in chunks],
            )
        return len(chunks)

    def replace_document(self, filename: str, chunks: list[TextChunk]) -> int:
        embeddings = embed_texts([chunk.content for chunk in chunks])
        with self._lock:
            self._collection.delete(where={"document_name": filename})
            if chunks:
                self._collection.upsert(
                    ids=[chunk.chunk_id for chunk in chunks],
                    documents=[chunk.content for chunk in chunks],
                    embeddings=embeddings,
                    metadatas=[chunk.metadata() for chunk in chunks],
                )
        return len(chunks)

    def delete_document(self, filename: str) -> int:
        with self._lock:
            existing = self._collection.get(
                where={"document_name": filename},
                include=[],
            )
            ids = existing.get("ids", [])
            if ids:
                self._collection.delete(ids=ids)
            return len(ids)

    def list_documents(self) -> list[StoredDocument]:
        records = self._collection.get(include=["metadatas"])
        grouped: dict[str, list[dict]] = {}
        for metadata in records.get("metadatas") or []:
            if not metadata:
                continue
            filename = str(metadata["document_name"])
            grouped.setdefault(filename, []).append(metadata)

        documents: list[StoredDocument] = []
        for filename, items in grouped.items():
            raw_created_at = str(items[0].get("created_at", ""))
            try:
                created_at = datetime.fromisoformat(raw_created_at)
            except ValueError:
                created_at = None
            documents.append(
                StoredDocument(
                    filename=filename,
                    chunk_count=len(items),
                    created_at=created_at,
                    document_hash=(
                        str(items[0]["document_hash"])
                        if items[0].get("document_hash")
                        else None
                    ),
                )
            )
        return sorted(documents, key=lambda item: item.filename.lower())

    def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        if self._collection.count() == 0:
            return []
        query_embedding = embed_texts([query])[0]
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        return [
            VectorSearchResult(
                content=document,
                distance=float(distance),
                metadata=metadata or {},
            )
            for document, metadata, distance in zip(
                documents,
                metadatas,
                distances,
                strict=True,
            )
        ]


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()
