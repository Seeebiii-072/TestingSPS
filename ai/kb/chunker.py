import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ai.config.settings import get_settings


SECTION_PATTERN = re.compile(r"(?m)^#\s+(.+?)\s*$")


@dataclass(frozen=True)
class TextChunk:
    content: str
    document_name: str
    section: str
    chunk_id: str
    source_path: str
    created_at: str
    index: int
    document_hash: str

    def metadata(self) -> dict[str, str | int]:
        return {
            "document_name": self.document_name,
            "section": self.section,
            "chunk_id": self.chunk_id,
            "source_path": self.source_path,
            "created_at": self.created_at,
            "chunk_index": self.index,
            "document_hash": self.document_hash,
        }


def _split_sections(text: str) -> list[tuple[str, str]]:
    matches = list(SECTION_PATTERN.finditer(text))
    if not matches:
        return [("General", text.strip())]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("Overview", preamble))

    for index, match in enumerate(matches):
        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[content_start:content_end].strip()))
    return sections


def _window_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(
                text.rfind("\n", start, end),
                text.rfind(". ", start, end),
                text.rfind(" ", start, end),
            )
            if boundary > start + (chunk_size // 2):
                end = boundary + 1

        content = text[start:end].strip()
        if content:
            chunks.append(content)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_text(
    text: str,
    document_name: str,
    *,
    source_path: str = "",
    created_at: datetime | str | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    settings = get_settings()
    resolved_chunk_size = chunk_size or settings.kb_chunk_size
    resolved_overlap = settings.kb_chunk_overlap if overlap is None else overlap
    if resolved_chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if resolved_overlap < 0 or resolved_overlap >= resolved_chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    timestamp = created_at or datetime.now(timezone.utc)
    if isinstance(timestamp, datetime):
        timestamp = timestamp.astimezone(timezone.utc).isoformat()

    chunks: list[TextChunk] = []
    document_hash = hashlib.sha256(
        (
            f"chunk_size={resolved_chunk_size}|overlap={resolved_overlap}|"
            f"{text}"
        ).encode("utf-8")
    ).hexdigest()
    for section, section_text in _split_sections(text):
        for content in _window_text(section_text, resolved_chunk_size, resolved_overlap):
            index = len(chunks)
            digest = hashlib.sha256(
                f"{document_name}|{section}|{index}|{content}".encode("utf-8")
            ).hexdigest()[:24]
            chunks.append(
                TextChunk(
                    content=content,
                    document_name=document_name,
                    section=section,
                    chunk_id=f"{document_name}:{digest}",
                    source_path=source_path,
                    created_at=timestamp,
                    index=index,
                    document_hash=document_hash,
                )
            )
    return chunks
