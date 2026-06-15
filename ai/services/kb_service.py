from datetime import datetime, timezone
from pathlib import Path

from ai.config.settings import get_settings
from ai.kb.chunker import chunk_text
from ai.kb.loader import DOCUMENTS_DIRECTORY, LoadedDocument, load_all_documents
from ai.kb.retriever import RetrievalResult, search as semantic_search
from ai.kb.vector_store import VectorStore, get_vector_store
from ai.schemas.kb import (
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseDocumentRequest,
    KnowledgeBaseDocumentResponse,
    KnowledgeBaseMutationResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResult,
)


def _safe_document_path(filename: str) -> Path:
    if (
        not filename
        or not filename.lower().endswith(".txt")
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
    ):
        raise ValueError("A plain .txt filename is required")

    directory = DOCUMENTS_DIRECTORY.resolve()
    path = (directory / filename).resolve()
    if path.parent != directory:
        raise ValueError("Document path must remain inside the KB documents directory")
    return path


def _chunks_for(document: LoadedDocument):
    return chunk_text(
        document.content,
        document.document_name,
        source_path=document.source_path,
        created_at=document.created_at,
    )


def index_document(
    filename: str,
    content: str,
    *,
    vector_store: VectorStore | None = None,
) -> int:
    path = _safe_document_path(filename)
    document = LoadedDocument(
        document_name=filename,
        content=content,
        source_path=str(path),
        created_at=datetime.now(timezone.utc),
    )
    chunks = _chunks_for(document)
    if not chunks:
        raise ValueError("Document content must contain indexable text")
    return (vector_store or get_vector_store()).replace_document(filename, chunks)


def index_all_documents(
    *,
    vector_store: VectorStore | None = None,
) -> dict[str, int]:
    store = vector_store or get_vector_store()
    indexed: dict[str, int] = {}
    documents = load_all_documents()
    filenames = {document.document_name for document in documents}
    stored_documents = {
        document.filename: document for document in store.list_documents()
    }
    for stored_document in stored_documents.values():
        if stored_document.filename not in filenames:
            store.delete_document(stored_document.filename)

    for document in documents:
        chunks = _chunks_for(document)
        if not chunks:
            continue
        stored = stored_documents.get(document.document_name)
        if (
            stored is not None
            and stored.document_hash == chunks[0].document_hash
            and stored.chunk_count == len(chunks)
        ):
            continue
        indexed[document.document_name] = store.replace_document(
            document.document_name,
            chunks,
        )
    return indexed


def delete_document(
    filename: str,
    *,
    vector_store: VectorStore | None = None,
) -> int:
    path = _safe_document_path(filename)
    store = vector_store or get_vector_store()
    deleted_chunks = store.delete_document(filename)
    if path.exists():
        path.unlink()
    elif deleted_chunks == 0:
        raise FileNotFoundError(f"Knowledge-base document not found: {filename}")
    return deleted_chunks


def update_document(
    filename: str,
    content: str,
    *,
    vector_store: VectorStore | None = None,
) -> int:
    path = _safe_document_path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"Knowledge-base document not found: {filename}")

    previous_content = path.read_text(encoding="utf-8-sig")
    chunk_count = index_document(filename, content, vector_store=vector_store)
    try:
        path.write_text(content, encoding="utf-8")
    except Exception:
        index_document(filename, previous_content, vector_store=vector_store)
        raise
    return chunk_count


def _search_response(
    results: list[RetrievalResult],
) -> KnowledgeBaseSearchResponse:
    if not results:
        return KnowledgeBaseSearchResponse(
            results=[],
            status="no_answer",
            answer_available=False,
            message="No sufficiently relevant knowledge-base content was found.",
        )

    return KnowledgeBaseSearchResponse(
        results=[
            KnowledgeBaseSearchResult(
                content=result.content,
                score=result.score,
                document_name=result.document_name,
                section=result.section,
                chunk_id=result.chunk_id,
                source_path=result.source_path,
                created_at=datetime.fromisoformat(result.created_at),
                citation=result.citation,
            )
            for result in results
        ],
        status="success",
        answer_available=True,
    )


def search(query: str, top_k: int | None = None) -> KnowledgeBaseSearchResponse:
    return _search_response(semantic_search(query, top_k))


class KnowledgeBaseService:
    def __init__(self, vector_store: VectorStore | None = None) -> None:
        self._vector_store = vector_store or get_vector_store()

    def create(
        self,
        request: KnowledgeBaseDocumentRequest,
    ) -> KnowledgeBaseMutationResponse:
        path = _safe_document_path(request.filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(
                f"Knowledge-base document already exists: {request.filename}"
            )

        path.write_text(request.content, encoding="utf-8")
        try:
            chunk_count = index_document(
                request.filename,
                request.content,
                vector_store=self._vector_store,
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return KnowledgeBaseMutationResponse(
            status="created",
            filename=request.filename,
            chunk_count=chunk_count,
        )

    def list_documents(self) -> list[KnowledgeBaseDocumentResponse]:
        return [
            KnowledgeBaseDocumentResponse(
                filename=document.filename,
                chunk_count=document.chunk_count,
                created_at=document.created_at,
            )
            for document in self._vector_store.list_documents()
        ]

    def delete(self, filename: str) -> KnowledgeBaseDeleteResponse:
        deleted_chunks = delete_document(
            filename,
            vector_store=self._vector_store,
        )
        return KnowledgeBaseDeleteResponse(
            status="deleted",
            filename=filename,
            deleted_chunks=deleted_chunks,
        )

    def update(
        self,
        filename: str,
        content: str,
    ) -> KnowledgeBaseMutationResponse:
        chunk_count = update_document(
            filename,
            content,
            vector_store=self._vector_store,
        )
        return KnowledgeBaseMutationResponse(
            status="updated",
            filename=filename,
            chunk_count=chunk_count,
        )

    def search(
        self,
        request: KnowledgeBaseSearchRequest,
    ) -> KnowledgeBaseSearchResponse:
        limit = request.top_k or get_settings().max_kb_results
        results = semantic_search(
            request.query,
            limit,
            vector_store=self._vector_store,
        )
        return _search_response(results)
