"""Embedding providers. `local` (default) needs no downloads; others are optional."""

from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.core.text import hashed_embedding

log = logging.getLogger("trustshield.embeddings")


class Embedder:
    name = "local-hash-768"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [hashed_embedding(t) for t in texts]


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # optional dependency

        self._model = SentenceTransformer(model)
        self.name = f"st-{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.encode(texts, normalize_embeddings=True)]


class OpenAIEmbedder(Embedder):
    def __init__(self, api_key: str, model: str, base_url: str = "") -> None:
        self.api_key, self.model = api_key, model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.name = f"openai-{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": texts},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    try:
        if s.embedding_provider == "sentence-transformers":
            return SentenceTransformerEmbedder()
        if s.embedding_provider == "openai" and s.openai_api_key:
            return OpenAIEmbedder(s.openai_api_key, s.embedding_model, s.openai_base_url)
    except Exception as exc:  # pragma: no cover - optional providers
        log.warning("Embedding provider %s unavailable (%s); using local hashed embeddings", s.embedding_provider, exc)
    return Embedder()
