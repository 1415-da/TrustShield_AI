"""PII and sensitive-data detection.

Microsoft Presidio supplies NER-based and built-in recognizers (PERSON, EMAIL_ADDRESS, PHONE_NUMBER,
CREDIT_CARD with Luhn validation, US_SSN, IBAN_CODE …). TrustShield registers additional custom pattern
recognizers for enterprise data that Presidio does not cover out of the box:

    SALARY_AMOUNT      currency amounts / LPA figures near compensation context
    CREDIT_CARD        card-like 13–19 digit numbers (Luhn-checked) — complements Presidio's recognizer
    BANK_ACCOUNT       9–18 digit account numbers near banking context, IFSC codes
    EMPLOYEE_ID        NovaCorp employee IDs (NC-12345)
    TEST_NATIONAL_ID   Aadhaar-like 12-digit identifiers (synthetic test identifiers only)
    CREDENTIAL         passwords / API keys / access tokens written inline

If Presidio or the spaCy model is unavailable, the same custom pattern definitions run through a
regex-only engine so the gateway keeps working (with reduced NER coverage).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.guardrails.types import Entity

log = logging.getLogger("trustshield.pii")

CONTEXT_WINDOW = 48  # characters searched either side of a match for context words
CONTEXT_BOOST = 0.35


@dataclass(frozen=True)
class PatternSpec:
    entity_type: str
    name: str
    regex: str
    score: float
    context: tuple[str, ...] = ()
    validate: str | None = None  # "luhn"
    flags: int = re.IGNORECASE


CUSTOM_PATTERNS: tuple[PatternSpec, ...] = (
    PatternSpec(
        "SALARY_AMOUNT", "currency_amount",
        r"(?:₹|\$|€|£|\bRs\.?\s?|\bINR\s?|\bUSD\s?)\s?\d{1,3}(?:[,\s]\d{2,3})*(?:\.\d+)?\s?(?:k|K|L|lakh|lakhs|lpa|LPA|cr|crore|million|M)?(?:\s?[–-]\s?(?:₹|\$)?\s?\d{1,3}(?:[,\s]\d{2,3})*(?:\.\d+)?\s?(?:k|L|lpa|LPA|lakh)?)?",
        0.45, ("salary", "salaries", "compensation", "ctc", "earn", "earns", "salary band", "pay band", "package", "income", "wage"),
    ),
    PatternSpec(
        "SALARY_AMOUNT", "lpa_figure",
        r"\b\d{1,3}(?:\.\d+)?\s?(?:[–-]\s?\d{1,3}(?:\.\d+)?\s?)?(?:LPA|lakhs? per annum|lakhs?)\b",
        0.75, ("salary", "compensation", "ctc", "band", "package"),
    ),
    PatternSpec(
        "CREDIT_CARD", "card_like_number",
        r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", 0.5,
        ("card", "credit", "debit", "visa", "mastercard", "amex", "corporate card"), validate="luhn",
    ),
    PatternSpec(
        "BANK_ACCOUNT", "account_number",
        r"(?<![\d-])\d{9,18}(?![\d-])", 0.2,
        ("account", "a/c", "acct", "bank", "ifsc", "routing", "beneficiary", "savings", "current account"),
    ),
    PatternSpec("BANK_ACCOUNT", "ifsc_code", r"\b[A-Z]{4}0[A-Z0-9]{6}\b", 0.75, ("ifsc", "bank", "branch"), flags=0),
    PatternSpec("EMPLOYEE_ID", "novacorp_employee_id", r"\bNC-\d{5}\b", 0.85, ("employee", "id", "staff"), flags=0),
    PatternSpec(
        "TEST_NATIONAL_ID", "aadhaar_like_12_digit",
        r"(?<!\d)(?<!\d[ -])\d{4}[ -]?\d{4}[ -]?\d{4}(?![ -]?\d)", 0.4,
        ("aadhaar", "aadhar", "uid", "national id", "identity", "test id", "test identifier"),
    ),
    PatternSpec("US_SSN", "ssn_like", r"\b\d{3}-\d{2}-\d{4}\b", 0.5, ("ssn", "social security")),
    PatternSpec("EMAIL_ADDRESS", "email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 0.85),
    PatternSpec(
        "PHONE_NUMBER", "phone_intl",
        r"(?<![\w-])(?:\+\d{1,3}[ -]?)?(?:\(\d{3}\)\s?|\d{3}[ -])\d{3}[ -]\d{4}(?![\w-])|(?<![\w])\+91[ -]?\d{5}[ -]?\d{5}(?!\d)",
        0.6, ("phone", "mobile", "call", "tel", "contact", "reach"),
    ),
    PatternSpec(
        "CREDENTIAL", "inline_secret",
        r"\b(?:password|passwd|pwd|passcode|api[_ -]?key|secret|token)\s*(?:is|=|:)\s*['\"]?[^\s'\"]{4,}",
        0.85,
    ),
    PatternSpec("CREDENTIAL", "provider_key", r"\b(?:sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})\b", 0.95, flags=0),
)

PRESIDIO_BUILTIN_ENTITIES = ("PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN", "IBAN_CODE", "IP_ADDRESS")


def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _has_context(text: str, start: int, end: int, words: tuple[str, ...]) -> bool:
    if not words:
        return False
    window = text[max(0, start - CONTEXT_WINDOW): end + CONTEXT_WINDOW].lower()
    return any(re.search(rf"\b{re.escape(w)}", window) for w in words)


def _regex_entities(text: str) -> list[Entity]:
    found: list[Entity] = []
    for spec in CUSTOM_PATTERNS:
        for m in re.finditer(spec.regex, text, spec.flags):
            raw = m.group(0).strip()
            if not raw:
                continue
            if spec.validate == "luhn" and not luhn_valid(raw):
                continue
            score = spec.score
            if _has_context(text, m.start(), m.end(), spec.context):
                score = min(1.0, score + CONTEXT_BOOST)
            found.append(Entity(spec.entity_type, m.start(), m.start() + len(raw), score, raw, "regex"))
    return found


def _resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    """Keep the highest-confidence entity for any overlapping span."""
    ordered = sorted(entities, key=lambda e: (-e.score, -(e.end - e.start)))
    kept: list[Entity] = []
    for ent in ordered:
        if all(ent.end <= k.start or ent.start >= k.end for k in kept):
            kept.append(ent)
    return sorted(kept, key=lambda e: e.start)


class PIIDetector:
    """Facade over Presidio (when available) plus TrustShield custom recognizers."""

    def __init__(self, use_presidio: bool = True, spacy_model: str = "en_core_web_sm") -> None:
        self.analyzer = None
        self.anonymizer = None
        self.engine_name = "regex"
        if use_presidio:
            self._init_presidio(spacy_model)

    def _init_presidio(self, spacy_model: str) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            from presidio_anonymizer import AnonymizerEngine

            provider = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": spacy_model}],
            })
            analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])
            # Register TrustShield recognizers inside Presidio so they appear in its registry.
            by_entity: dict[str, list[PatternSpec]] = {}
            for spec in CUSTOM_PATTERNS:
                if spec.validate is None and spec.flags == re.IGNORECASE:
                    by_entity.setdefault(spec.entity_type, []).append(spec)
            for entity_type, specs in by_entity.items():
                context = sorted({w for s in specs for w in s.context})
                analyzer.registry.add_recognizer(PatternRecognizer(
                    supported_entity=entity_type,
                    name=f"TrustShield{entity_type.title().replace('_', '')}Recognizer",
                    patterns=[Pattern(s.name, f"(?i){s.regex}", s.score) for s in specs],
                    context=context or None,
                ))
            self.analyzer = analyzer
            self.anonymizer = AnonymizerEngine()
            self.engine_name = "presidio"
        except Exception as exc:  # pragma: no cover - depends on environment
            log.warning("Presidio unavailable, using regex-only PII engine: %s", exc)

    def analyze(self, text: str, min_score: float = 0.3) -> list[Entity]:
        if not text:
            return []
        entities = _regex_entities(text)
        if self.analyzer is not None:
            try:
                results = self.analyzer.analyze(text=text, language="en", entities=list(PRESIDIO_BUILTIN_ENTITIES))
                for r in results:
                    raw = text[r.start:r.end]
                    if r.entity_type == "PERSON" and (len(raw) < 3 or not raw[0].isupper()):
                        continue
                    entities.append(Entity(r.entity_type, r.start, r.end, float(r.score), raw, "presidio"))
            except Exception as exc:  # pragma: no cover
                log.warning("Presidio analysis failed, regex results only: %s", exc)
        return [e for e in _resolve_overlaps(entities) if e.score >= min_score]

    def anonymize(self, text: str, entities: list[Entity]) -> str:
        """Replace each entity span with `<ENTITY_TYPE>`."""
        if not entities:
            return text
        if self.anonymizer is not None:
            try:
                from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

                results = [RecognizerResult(e.entity_type, e.start, e.end, e.score) for e in entities]
                operators = {e.entity_type: OperatorConfig("replace", {"new_value": f"<{e.entity_type}>"}) for e in entities}
                return self.anonymizer.anonymize(text=text, analyzer_results=results, operators=operators).text
            except Exception as exc:  # pragma: no cover
                log.warning("Presidio anonymizer failed, using fallback: %s", exc)
        out = text
        for e in sorted(entities, key=lambda x: x.start, reverse=True):
            out = out[: e.start] + f"<{e.entity_type}>" + out[e.end:]
        return out


@lru_cache
def get_pii_detector() -> PIIDetector:
    settings = get_settings()
    return PIIDetector(use_presidio=settings.presidio_enabled, spacy_model=settings.spacy_model)
