"""Grounding and confidence *risk signals*.

These scores estimate how well a draft answer is supported by the evidence TrustShield retrieved. They
are heuristics — lexical overlap, hashed-vector similarity, citation presence, evidence coverage and
simple contradiction cues — and are presented in the product as risk signals, never as a guarantee that
an answer is true or as a hallucination detector.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.core.text import GENERIC_QUERY_TERMS, content_terms, cosine, hashed_embedding, numbers_in

HEDGES = (
    r"\bprobably\b", r"\blikely\b", r"\bmight\b", r"\bperhaps\b", r"\bi think\b", r"\bi believe\b", r"\bgenerally\b",
    r"\btypically\b", r"\busually\b", r"\bit seems\b", r"\bpossibly\b", r"\bnot sure\b",
)
NO_EVIDENCE = (
    r"couldn'?t find", r"could not find", r"no (specific |explicit )?policy", r"does(n'?t| not) (mention|cover|address)",
    r"not covered", r"unable to find",
)

W_SEMANTIC, W_LEXICAL, W_CITATION, W_COVERAGE, W_QUERY = 0.30, 0.20, 0.15, 0.15, 0.20


@dataclass
class GroundingSignals:
    semantic_similarity: float = 0.0
    lexical_support: float = 0.0
    citation_presence: float = 0.0
    evidence_coverage: float = 0.0
    query_support: float = 0.0
    contradiction_penalty: float = 0.0
    groundedness: float = 0.0
    retrieval_similarity: float = 0.0
    length_score: float = 0.0
    input_risk: float = 0.0
    confidence: float = 0.0
    unsupported_terms: list[str] = field(default_factory=list)
    unsupported_numbers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def public(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 3)
        d["label"] = "risk signal — not a guarantee of correctness"
        return d


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def assess_grounding(
    query: str,
    response: str,
    evidence: list[str],
    retrieval_similarity: float,
    input_risk: float = 0.0,
) -> GroundingSignals:
    sig = GroundingSignals(retrieval_similarity=round(retrieval_similarity, 3), input_risk=input_risk)
    resp_terms = content_terms(response)
    words = len(response.split())
    sig.length_score = 1.0 if 15 <= words <= 350 else (0.5 if words < 15 else 0.7)

    if not evidence or not resp_terms:
        sig.notes.append("no evidence retrieved" if not evidence else "empty response")
        sig.confidence = round(0.1 * sig.length_score + 0.1 * (1 - input_risk), 3)
        return sig

    evidence_text = "\n".join(evidence)
    ev_terms = set(content_terms(evidence_text))

    sig.semantic_similarity = _clamp(cosine(hashed_embedding(response), hashed_embedding(evidence_text)) / 0.6)
    resp_set = set(resp_terms)
    sig.lexical_support = len(resp_set & ev_terms) / len(resp_set)

    cited = {int(n) for n in re.findall(r"\[(\d{1,2})\]", response)}
    sig.citation_presence = 1.0 if cited and all(1 <= n <= len(evidence) for n in cited) else 0.0

    top_terms = [t for t in dict.fromkeys(content_terms(evidence[0]))][:40]
    sig.evidence_coverage = _clamp(len(resp_set & set(top_terms)) / 10) if top_terms else 0.0

    q_terms = [t for t in dict.fromkeys(content_terms(query)) if t not in GENERIC_QUERY_TERMS]
    if q_terms:
        unsupported = [t for t in q_terms if t not in ev_terms]
        sig.unsupported_terms = unsupported
        sig.query_support = 1.0 - len(unsupported) / len(q_terms)
    else:
        sig.query_support = 1.0

    penalty = 0.0
    ev_numbers = numbers_in(evidence_text)
    stray = sorted(n for n in numbers_in(response) if n not in ev_numbers and not re.fullmatch(r"[1-9]", n))
    if stray:
        sig.unsupported_numbers = stray[:5]
        penalty += min(0.3, 0.1 * len(stray))
        sig.notes.append("numbers not found in evidence")
    hedges = sum(1 for h in HEDGES if re.search(h, response, re.IGNORECASE))
    if hedges:
        penalty += min(0.2, 0.05 * hedges)
        sig.notes.append("hedging language")
    if any(re.search(p, response, re.IGNORECASE) for p in NO_EVIDENCE):
        penalty += 0.15
        sig.notes.append("answer states evidence is missing")
    if sig.unsupported_terms:
        sig.notes.append("question terms not found in evidence: " + ", ".join(sig.unsupported_terms[:4]))
    sig.contradiction_penalty = round(penalty, 3)

    sig.groundedness = _clamp(
        W_SEMANTIC * sig.semantic_similarity
        + W_LEXICAL * sig.lexical_support
        + W_CITATION * sig.citation_presence
        + W_COVERAGE * sig.evidence_coverage
        + W_QUERY * sig.query_support
        - penalty
    )
    sig.confidence = round(
        _clamp(0.6 * sig.groundedness + 0.2 * _clamp(retrieval_similarity) + 0.1 * sig.length_score + 0.1 * (1 - input_risk)),
        3,
    )
    sig.groundedness = round(sig.groundedness, 3)
    return sig
