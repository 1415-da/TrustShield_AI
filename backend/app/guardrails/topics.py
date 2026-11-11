"""Sensitive-topic classification.

A deliberately transparent classifier: every topic has a weighted lexicon combined with a noisy-OR,
then adjusted by intent modifiers that distinguish *asking for someone's data* from *asking about a
policy*:

    + target    the prompt points at a specific person or at everyone ("Ravi's", "all salaries")
    + request   the prompt asks for data to be produced ("show", "what is", "email me", "export")
    + system    (credentials only) the prompt names a system ("production database", "VPN")
    − meta      the prompt is about process or policy ("what is the salary *policy*", "how do I …")
    − self      the prompt is about the asker's own data and names nobody else ("my bank details")

Thresholds and resulting actions live in policy rules, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.guardrails.injection import score_injection
from app.guardrails.types import Entity, TopicScore

LEXICON: dict[str, list[tuple[str, float]]] = {
    "salary": [
        (r"\bsalar(y|ies)\b", 0.5), (r"\bpay ?slips?\b", 0.45), (r"\bctc\b", 0.45), (r"\bwages?\b", 0.4),
        (r"\bhow much (does|do|is) .{1,40}\b(earn|make|paid|get paid)\b", 0.6), (r"\bearn(s|ing)?\b", 0.25),
        (r"\btake[- ]home\b", 0.4), (r"\b(pay|salary) (band|grade|range)s?\b", 0.5), (r"\bpaid\b", 0.15),
    ],
    "compensation": [
        (r"\bcompensation\b", 0.45), (r"\bbonus(es)?\b", 0.35), (r"\b(esops?|rsus?|stock options?)\b", 0.35),
        (r"\b(salary|pay) bands?\b", 0.45), (r"\b(increment|appraisal|hike|raise)s?\b", 0.3), (r"\bsalar(y|ies)\b", 0.3),
    ],
    "credit_card": [
        (r"\bcredit cards?\b", 0.5), (r"\bcard (number|details|no\.?)s?\b", 0.55), (r"\bcvv\b|\bcvc\b", 0.6),
        (r"\bexpiry date\b", 0.3), (r"\bdebit cards?\b", 0.45), (r"\bcorporate cards?\b", 0.3),
    ],
    "bank_details": [
        (r"\bbank (details|info|information)\b", 0.55), (r"\bbank accounts?\b", 0.5), (r"\baccount (number|no\.?)s?\b", 0.5),
        (r"\bifsc\b", 0.5), (r"\brouting numbers?\b", 0.5), (r"\biban\b", 0.5), (r"\bswift code\b", 0.35),
    ],
    "pii": [
        (r"\bphone numbers?\b|\bmobile numbers?\b", 0.35), (r"\bhome address(es)?\b", 0.5), (r"\bpersonal email\b", 0.4),
        (r"\bdate of birth\b|\bdob\b|\bbirthday\b", 0.45), (r"\baadhaa?r\b", 0.55), (r"\bssns?\b|\bsocial security\b", 0.55),
        (r"\bnational ids?\b", 0.5), (r"\bpassport (number|details)\b", 0.45), (r"\bcontact details\b", 0.25),
        (r"\bmedical (records?|history|condition)\b", 0.5),
    ],
    "legal_advice": [
        (r"\blegal advice\b", 0.6), (r"\b(sue|suing|lawsuit|litigation)\b", 0.5), (r"\bis (it|this|that) legal\b", 0.5),
        (r"\bcan i be (fired|terminated)\b", 0.45), (r"\bbreach of contract\b", 0.45), (r"\b(lawyer|attorney)\b", 0.35),
        (r"\b(liable|liability)\b", 0.35), (r"\bpress charges\b", 0.5), (r"\bwrongful (termination|dismissal)\b", 0.5),
    ],
    "security_credentials": [
        (r"\bpasswords?\b|\bpasswd\b", 0.5), (r"\bcredentials?\b", 0.5), (r"\bapi[ _-]?keys?\b", 0.55),
        (r"\bsecret (key|token)s?\b", 0.55), (r"\b(access|auth|bearer) tokens?\b", 0.4), (r"\bprivate keys?\b", 0.55),
        (r"\bssh keys?\b", 0.5), (r"\b(root|admin) (access|password|login)\b", 0.45), (r"\blogin details\b", 0.45),
        (r"\b(mfa|otp|2fa) codes?\b", 0.4),
    ],
}

TOPICS = tuple(LEXICON) + ("prompt_injection",)
PERSONAL_DATA_TOPICS = {"salary", "compensation", "credit_card", "bank_details", "pii"}

TARGET_PATTERNS = [
    r"\b(all|every|each) (employees?|staff|colleagues?|people|salaries|accounts|cards|records)\b",
    r"\beveryone'?s\b", r"\b(his|her|their)\b", r"\b(colleague|coworker|co-worker|manager|boss|teammate)'?s?\b",
    r"\b(of|for) (the )?(whole|entire) (team|company|department)\b", r"\bon file\b",
]
REQUEST_PATTERNS = [
    r"\b(show|give|tell|list|reveal|share|send|email|export|find|look ?up|get|provide|fetch|display|print|dump)\b",
    r"\bwhat(?:'s| is| are)\b", r"\bhow much\b",
]
META_PATTERNS = [
    r"\bpolic(y|ies)\b", r"\bprocess\b", r"\bprocedure\b", r"\bhow (do|can|should) i\b", r"\bhow to\b",
    r"\bwho (can|approves|should)\b", r"\bguidelines?\b", r"\bconfidential(ity)?\b", r"\breset\b",
    r"\bupdate my\b", r"\bchange my\b", r"\bwhen (is|are|do|does)\b", r"\breimburse",
    r"\b(minimum|maximum|length|requirements?|complexity|rotation|expiry|how often)\b",
]
SELF_PATTERNS = [r"\b(my|mine|i|i'm|i've|me)\b"]
SYSTEM_PATTERNS = [
    r"\b(production|prod|staging)\b", r"\bdatabase\b|\bdb\b", r"\b(server|cluster|vpn|wifi|wi-fi|router|firewall)\b",
    r"\b(admin|root|service) account\b", r"\b(aws|azure|gcp|github|jira|okta)\b",
]

MOD_TARGET, MOD_REQUEST, MOD_SYSTEM, MOD_META, MOD_SELF = 0.3, 0.15, 0.25, -0.35, -0.2


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


@dataclass
class TopicAnalysis:
    scores: dict[str, TopicScore]
    target_people: list[str] = field(default_factory=list)

    def score(self, topic: str) -> float:
        ts = self.scores.get(topic)
        return ts.score if ts else 0.0

    def public(self) -> dict[str, dict]:
        return {k: {"score": round(v.score, 3), "signals": v.signals} for k, v in self.scores.items() if v.score > 0}


# Capitalised possessives that are not people ("Friday's payment run", "NovaCorp's policy").
NON_PERSON_POSSESSIVES = frozenset(
    "NovaCorp TrustShield Today Tomorrow Yesterday Company India It What That This Team Finance Legal HR IT Engineering "
    "Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August "
    "September October November December Q1 Q2 Q3 Q4 Year Month Week".split()
)


ORG_SUFFIXES = frozenset(
    "supplies supply ltd limited inc corp corporation llc llp pvt plc co technologies technology solutions services systems "
    "traders trading industries enterprises group logistics labs partners holdings consulting".split()
)


def find_target_people(text: str, directory_names: list[str], entities: list[Entity]) -> list[str]:
    """People the prompt points at: synthetic directory names, possessive names, or NER PERSON entities."""
    found: list[str] = []
    lowered = text.lower()
    for name in directory_names:
        parts = name.split()
        if name.lower() in lowered or (parts and re.search(rf"\b{re.escape(parts[0])}\b", text)):
            found.append(name)
    for m in re.finditer(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)'s\b", text):
        candidate = m.group(1)
        if candidate.split()[0] not in NON_PERSON_POSSESSIVES and not any(
            candidate.split()[0] in f for f in found
        ):
            found.append(candidate)
    for e in entities:
        if e.entity_type != "PERSON" or e.score < 0.6 or any(e.text.split()[0] in f for f in found):
            continue
        # The small spaCy model sometimes labels organisations as people ("Orion Supplies"); skip obvious ones.
        last = e.text.split()[-1].strip(".,").lower()
        preceding = text[max(0, e.start - 14):e.start].lower()
        if last in ORG_SUFFIXES or re.search(r"\b(vendor|supplier|client|company|customer|firm)\s*$", preceding):
            continue
        found.append(e.text)
    return found


def classify_topics(text: str, entities: list[Entity] | None = None, directory_names: list[str] | None = None) -> TopicAnalysis:
    entities = entities or []
    lowered = text.lower()
    targets = find_target_people(text, directory_names or [], entities)
    has_target = bool(targets) or _any(TARGET_PATTERNS, lowered)
    has_request = _any(REQUEST_PATTERNS, lowered)
    has_meta = _any(META_PATTERNS, lowered)
    has_self = _any(SELF_PATTERNS, lowered) and not has_target
    has_system = _any(SYSTEM_PATTERNS, lowered)
    # Only context-confirmed entities (score ≥ 0.7) count as topic evidence; a bare "$80" is not salary data.
    entity_types = {e.entity_type for e in entities if e.score >= 0.7}

    scores: dict[str, TopicScore] = {}
    for topic, lexicon in LEXICON.items():
        remaining, signals = 1.0, []
        for pattern, weight in lexicon:
            m = re.search(pattern, lowered)
            if m:
                remaining *= 1.0 - weight
                signals.append(m.group(0))
        base = 1.0 - remaining
        # A detected entity of the matching type is strong evidence for the topic.
        entity_hint = {"credit_card": "CREDIT_CARD", "bank_details": "BANK_ACCOUNT", "security_credentials": "CREDENTIAL",
                       "salary": "SALARY_AMOUNT"}.get(topic)
        if entity_hint and entity_hint in entity_types:
            base = max(base, 0.45)
            signals.append(f"entity:{entity_hint}")
        if base == 0.0:
            scores[topic] = TopicScore(topic, 0.0, [])
            continue
        score = base
        if topic in PERSONAL_DATA_TOPICS or topic == "security_credentials":
            if has_target and topic != "security_credentials":
                score += MOD_TARGET
                signals.append("target:" + (targets[0] if targets else "group"))
            if has_request:
                score += MOD_REQUEST
                signals.append("request")
            if has_meta:
                score += MOD_META if not has_target else MOD_META / 2
                signals.append("policy-meta")
            if has_self:
                score += MOD_SELF
                signals.append("self")
            if topic == "security_credentials" and has_system:
                score += MOD_SYSTEM
                signals.append("system")
        scores[topic] = TopicScore(topic, round(max(0.0, min(1.0, score)), 3), signals)

    scores["prompt_injection"] = score_injection(text)
    return TopicAnalysis(scores=scores, target_people=targets)
