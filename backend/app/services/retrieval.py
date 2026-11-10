"""Hybrid retrieval over indexed policy chunks.

Score = 0.55 × cosine(query, chunk embedding) + 0.45 × saturated BM25. Embeddings are stored as JSON on
`document_chunks` and scored in-process — appropriate for an MVP-sized corpus. The index is cached and
rebuilt when documents change.
"""

from __future__ import annotations

import math
import threading
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.text import content_terms, cosine
from app.models import Document, DocumentChunk
from app.services.embeddings import get_embedder

W_COS, W_BM25, MIN_SCORE = 0.55, 0.45, 0.12
RELATIVE_CUTOFF = 0.5  # drop chunks scoring below half of the best match
K1, B = 1.4, 0.75


@dataclass
class IndexedChunk:
    chunk_id: int
    document_id: int
    title: str
    heading: str
    text: str
    embedding: list[float]
    terms: Counter
    length: int
    trust_level: str


@dataclass
class RetrievedChunk:
    chunk: IndexedChunk
    score: float
    cosine: float
    bm25: float


class _Index:
    def __init__(self) -> None:
        self.signature: tuple | None = None
        self.chunks: list[IndexedChunk] = []
        self.df: Counter = Counter()
        self.avg_len = 1.0
        self.lock = threading.Lock()


_index = _Index()


def invalidate() -> None:
    _index.signature = None


def _load(db: Session) -> None:
    sig = tuple(db.execute(select(func.count(DocumentChunk.id), func.max(DocumentChunk.id), func.max(Document.indexed_at))
                           .select_from(DocumentChunk).join(Document)).one())
    if sig == _index.signature:
        return
    with _index.lock:
        rows = db.execute(
            select(DocumentChunk, Document.title, Document.trust_level)
            .join(Document).where(Document.status == "indexed")
        ).all()
        chunks = []
        for chunk, title, trust in rows:
            terms = Counter(content_terms(f"{title} {chunk.heading} {chunk.text}"))
            chunks.append(IndexedChunk(chunk.id, chunk.document_id, title, chunk.heading, chunk.text,
                                       chunk.embedding or [], terms, sum(terms.values()), trust))
        _index.chunks = chunks
        _index.df = Counter(t for c in chunks for t in c.terms)
        _index.avg_len = (sum(c.length for c in chunks) / len(chunks)) if chunks else 1.0
        _index.signature = sig


def search(db: Session, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    _load(db)
    if not _index.chunks:
        return []
    top_k = top_k or get_settings().retrieval_top_k
    q_terms = content_terms(query)
    q_vec = get_embedder().embed([query])[0]
    n = len(_index.chunks)
    results: list[RetrievedChunk] = []
    for c in _index.chunks:
        bm25 = 0.0
        for t in set(q_terms):
            tf = c.terms.get(t, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - _index.df[t] + 0.5) / (_index.df[t] + 0.5))
            bm25 += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * c.length / _index.avg_len))
        cos = max(0.0, cosine(q_vec, c.embedding))
        bm25_sat = 1 - math.exp(-bm25 / 6)
        score = W_COS * cos + W_BM25 * bm25_sat
        if score >= MIN_SCORE:
            results.append(RetrievedChunk(c, round(score, 4), round(cos, 4), round(bm25, 3)))
    results.sort(key=lambda r: -r.score)
    if results:
        floor = results[0].score * RELATIVE_CUTOFF
        results = [r for r in results if r.score >= floor]
    return results[:top_k]
