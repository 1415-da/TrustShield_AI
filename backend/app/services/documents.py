"""Document ingestion: validation, chunking, and (re)indexing."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.core.security import sha256_hex
from app.core.text import content_terms
from app.models import Document, DocumentChunk, User
from app.models.base import utcnow
from app.services import retrieval
from app.services.embeddings import get_embedder

MAX_CHARS = 700
ALLOWED_EXTENSIONS = (".md", ".markdown", ".txt", ".pdf", ".text")
MAX_UPLOAD_BYTES = 1_000_000


def decode_upload(filename: str, raw: bytes) -> tuple[str, str]:
    """Return (text, content_type). Accepts Markdown/TXT and *text-extractable* PDF-like files."""
    lower = filename.lower()
    if not lower.endswith(ALLOWED_EXTENSIONS):
        raise BadRequest("Unsupported file type. Upload .md, .txt, or plain-text .pdf documents.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise BadRequest("File too large (max 1 MB).")
    if raw.startswith(b"%PDF"):
        raise BadRequest("Binary PDFs are not supported in the MVP. Export the policy as Markdown or plain text.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise BadRequest("File is not valid UTF-8 text.") from None
    if len(text.strip()) < 40:
        raise BadRequest("Document is empty or too short to index.")
    content_type = "text/markdown" if lower.endswith((".md", ".markdown")) else "text/plain"
    return text, content_type


def chunk_text(text: str) -> list[tuple[str, str]]:
    """Paragraph-aware chunking. Returns (heading, chunk_text); headings stay with their body."""
    chunks: list[tuple[str, str]] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            body = "\n\n".join(buffer).strip()
            if body:
                chunks.append((heading, body))

    for para in re.split(r"\n\s*\n", text.strip()):
        para = para.strip()
        if not para:
            continue
        if re.match(r"^#{1,6}\s", para):
            lines = para.splitlines()
            flush()
            buffer = []
            heading = lines[0].lstrip("#").strip()
            rest = "\n".join(lines[1:]).strip()
            if rest:
                buffer.append(rest)
            continue
        if buffer and sum(len(b) for b in buffer) + len(para) > MAX_CHARS:
            last = buffer[-1]
            flush()
            buffer = [last] if len(last) < MAX_CHARS // 2 else []
        buffer.append(para)
    flush()
    return chunks


def index_document(db: Session, doc: Document) -> Document:
    doc.chunks.clear()
    db.flush()
    pieces = chunk_text(doc.content)
    embedder = get_embedder()
    vectors = embedder.embed([f"{doc.title}. {h}. {t}" for h, t in pieces]) if pieces else []
    for i, ((heading, text), vec) in enumerate(zip(pieces, vectors)):
        doc.chunks.append(DocumentChunk(ordinal=i, heading=heading, text=text, embedding=vec, token_count=len(content_terms(text))))
    doc.chunk_count = len(pieces)
    doc.status = "indexed"
    doc.indexed_at = utcnow()
    db.commit()
    retrieval.invalidate()
    return doc


def create_document(
    db: Session, *, title: str, filename: str, content: str, content_type: str, trust_level: str = "trusted",
    source: str = "upload", user: User | None = None,
) -> Document:
    doc = Document(
        title=title.strip()[:300], filename=filename[:300], content=content, content_type=content_type,
        trust_level=trust_level if trust_level in ("trusted", "untrusted") else "trusted", source=source,
        content_hash=sha256_hex(content), status="processing", uploaded_by=user.id if user else None,
    )
    db.add(doc)
    db.commit()
    return doc
