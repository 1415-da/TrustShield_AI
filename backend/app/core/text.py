"""Small, dependency-free text utilities shared by retrieval, grounding and the mock LLM."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before being below between both
    but by can could did do does doing down during each few for from further had has have having he her here hers
    herself him himself his how i if in into is it its itself just me more most my myself no nor not now of off on
    once only or other our ours ourselves out over own same she should so some such than that the their theirs them
    themselves then there these they this those through to too under until up very was we were what when where which
    while who whom why will with would you your yours yourself yourselves also may might must shall within per via
    please tell show give get let us one two three etc e g ie""".split()
)

# Words too generic to say whether a question is covered by evidence.
GENERIC_QUERY_TERMS = frozenset(
    "novacorp policy policies company employee employees rule rules guideline guidelines process procedure need know "
    "summarize summarise explain describe question answer help much many like want say says said work".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def stem(token: str) -> str:
    """Very light suffix stripping — enough to match refund/refunds/refunded."""
    for suffix in ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ied", "ers", "er", "es", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            base = token[: -len(suffix)]
            return base + "y" if suffix in ("ies", "ied") else base
    return token


def tokenize(text: str) -> list[str]:
    return [t.replace("'s", "") for t in _TOKEN_RE.findall(text.lower())]


def content_terms(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS and len(t) > 2 and not t.isdigit()]


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text) if len(n.replace(",", "")) >= 1}


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(•-])|\n+", text)
    return [p.strip(" -•\t") for p in parts if len(p.strip()) > 12]


HASH_DIM = 768


def hashed_embedding(text: str, dim: int = HASH_DIM) -> list[float]:
    """Deterministic hashed unigram+bigram TF vector (sublinear tf, L2-normalised)."""
    terms = content_terms(text)
    grams = terms + [f"{a}_{b}" for a, b in zip(terms, terms[1:])]
    counts = Counter(grams)
    vec = [0.0] * dim
    for gram, count in counts.items():
        h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16)
        sign = 1.0 if (h >> 1) & 1 else -1.0
        vec[h % dim] += sign * (1.0 + math.log(count)) * (0.6 if "_" in gram else 1.0)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
