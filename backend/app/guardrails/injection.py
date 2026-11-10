"""Prompt-injection risk scoring.

Rather than a single keyword list, each signal family carries a weight and the families are combined
with a noisy-OR: `score = 1 - Π(1 - wᵢ)`. Multiple weak signals therefore add up, while a single strong
signal (e.g. an explicit instruction override) is enough on its own. Text is also normalised to undo
simple obfuscation (leetspeak, spacing) and matched a second time.

The resulting score feeds the `prompt_injection` topic; the *threshold* and *action* are policy rules in
the database, so admins tune sensitivity without code changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.guardrails.types import TopicScore


@dataclass(frozen=True)
class InjectionSignal:
    name: str
    pattern: str
    weight: float


SIGNALS: tuple[InjectionSignal, ...] = (
    InjectionSignal(
        "instruction_override",
        r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|any|your|the|these|those|system)\b.{0,25}\b(instructions?|rules?|prompts?|guidelines?|directives?|policies|constraints)\b",
        0.72,
    ),
    InjectionSignal(
        "system_prompt_extraction",
        r"\b(reveal|show|print|repeat|display|leak|output|tell me|what is|what's|give me)\b.{0,30}\b(system|hidden|initial|original|developer|internal)\s+(prompt|instructions?|message|configuration)",
        0.75,
    ),
    InjectionSignal(
        "safety_disable",
        r"\b(disable|turn off|switch off|bypass|deactivate|remove|ignore|skip|circumvent)\b.{0,30}\b(safety|guardrails?|filters?|restrictions?|content polic(?:y|ies)|moderation|trustshield|redaction|security checks?)\b",
        0.7,
    ),
    InjectionSignal(
        "role_play_jailbreak",
        r"\b(you are now|act as|pretend (?:to be|you are)|roleplay as|from now on,? you)\b.{0,50}\b(dan|unrestricted|unfiltered|jailbroken|developer mode|no (?:rules|restrictions|limits|filters)|evil)\b",
        0.68,
    ),
    InjectionSignal("privileged_mode", r"\b(developer|god|debug|admin|sudo|maintenance)\s+mode\b", 0.4),
    InjectionSignal(
        "delimiter_injection",
        r"(```\s*system|<\s*/?\s*(system|instructions?)\s*>|\[/?INST\]|^\s*#{2,}\s*(system|instruction)|\bend of (system )?prompt\b)",
        0.5,
    ),
    InjectionSignal("new_instructions", r"\b(new|updated|real|actual|secret)\s+instructions?\s*[:\-]", 0.45),
    InjectionSignal(
        "authority_claim",
        r"\b(i am|i'm|this is)\s+(the|an?|your)\s+(admin|administrator|developer|ceo|cto|security officer|system owner)\b",
        0.3,
    ),
    InjectionSignal(
        "assistant_directive",
        r"\b(assistant|ai|model|chatbot)\b.{0,20}\b(must|should|will)\b.{0,20}\b(reveal|disclose|share|comply|answer anything|obey)\b",
        0.45,
    ),
    InjectionSignal(
        "confidential_disclosure",
        r"\b(reveal|disclose|leak|dump|expose)\b.{0,30}\b(confidential|secret|sensitive|private|restricted|all)\s+(data|information|records|details|salaries|files)\b",
        0.4,
    ),
    InjectionSignal("encoded_payload", r"\b[A-Za-z0-9+/]{48,}={0,2}\b", 0.3),
)

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def _normalise(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.lower())
    return collapsed.translate(_LEET)


def score_injection(text: str) -> TopicScore:
    """Return the prompt-injection risk score in [0, 1] with the signal names that fired."""
    if not text:
        return TopicScore("prompt_injection", 0.0, [])
    plain = re.sub(r"\s+", " ", text.lower())
    deobfuscated = _normalise(text)
    fired: list[str] = []
    remaining = 1.0
    for sig in SIGNALS:
        flags = re.IGNORECASE | re.MULTILINE
        hit_plain = re.search(sig.pattern, plain, flags) is not None
        hit_obf = not hit_plain and sig.name != "encoded_payload" and re.search(sig.pattern, deobfuscated, flags) is not None
        if hit_plain or hit_obf:
            fired.append(sig.name + (" (obfuscated)" if hit_obf else ""))
            remaining *= 1.0 - sig.weight
    score = 1.0 - remaining
    if len(fired) >= 3:
        score = min(1.0, score + 0.05)
    return TopicScore("prompt_injection", round(score, 3), fired)
