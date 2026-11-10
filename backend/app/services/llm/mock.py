"""Deterministic offline provider.

Composes answers by extracting the context sentences that best match the question, with [n] citations,
so the full pipeline — retrieval, grounding, output guardrails — can be demonstrated without an API key.

Behaviour worth knowing for demos and tests:
* If key question terms are absent from every context block (e.g. "Martian vendor refunds"), it produces
  a hedged, uncited answer. That is the designated low-confidence path the grounding signal should catch.
* Directory blocks (synthetic people data) are summarised field-by-field. Contact details pass through so
  the *output* guardrails can demonstrate redaction; the mock never invents personal data.
"""

from __future__ import annotations

import re
import time

from app.core.text import GENERIC_QUERY_TERMS, content_terms, split_sentences
from app.services.llm.base import LLMProvider, LLMResponse

_BLOCK_RE = re.compile(r"^\[(\d+)\] (.+?)\n(.*?)(?=^\[\d+\] |\Z)", re.S | re.M)
DIRECTORY_TITLE = "NovaCorp People Directory (synthetic)"


class MockProvider(LLMProvider):
    name = "mock"
    model = "trustshield-mock-1"

    def generate(self, prompt: str, context: list[str]) -> LLMResponse:
        t0 = time.perf_counter()
        blocks = []
        for raw in context:
            m = _BLOCK_RE.match(raw.strip() + "\n")
            if m:
                blocks.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
        text = self._compose(prompt, blocks)
        return LLMResponse(
            text=text, provider=self.name, model=self.model,
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            prompt_tokens=sum(len(c.split()) for c in context) + len(prompt.split()),
            completion_tokens=len(text.split()),
        )

    # ------------------------------------------------------------------
    def _compose(self, prompt: str, blocks: list[tuple[int, str, str]]) -> str:
        directory = [b for b in blocks if b[1].startswith(DIRECTORY_TITLE)]
        policy_blocks = [b for b in blocks if not b[1].startswith(DIRECTORY_TITLE)]
        if directory:
            return self._directory_answer(prompt, directory)
        if not policy_blocks:
            return (
                "I couldn't find a NovaCorp policy that covers this question. It might be handled case by case, "
                "so please check with the relevant policy owner before acting."
            )

        q_terms = [t for t in dict.fromkeys(content_terms(prompt)) if t not in GENERIC_QUERY_TERMS]
        vocab = set(content_terms(" ".join(f"{b[1]} {b[2]}" for b in policy_blocks)))
        missing = [t for t in q_terms if t not in vocab]

        scored: list[tuple[float, int, str]] = []
        for rank, (idx, _title, body) in enumerate(policy_blocks):
            for sent in split_sentences(body):
                terms = set(content_terms(sent))
                overlap = len(terms & set(q_terms))
                if overlap:
                    scored.append((overlap + 0.3 / (rank + 1), idx, sent))
        scored.sort(key=lambda s: -s[0])

        if q_terms and len(missing) / len(q_terms) >= 0.3 or not scored:
            topic = ", ".join(missing[:3]) or "this request"
            hint = scored[0][2] if scored else policy_blocks[0][2].split(".")[0]
            hint = hint.rstrip(".")
            return (
                f"I couldn't find anything in NovaCorp's policies that specifically covers {topic}. "
                f"The closest related guidance probably applies, which says: \"{hint}.\" "
                "However, this might not apply to your situation, so I'd treat it as likely rather than definitive."
            )

        chosen: list[tuple[int, str]] = []
        for _score, idx, sent in scored:
            if len(chosen) == 3:
                break
            if all(sent != c[1] for c in chosen):
                chosen.append((idx, sent))
        lead_title = next(t for i, t, _ in policy_blocks if i == chosen[0][0])
        lines = [f"Based on the {lead_title.split(' — ')[0]}:", ""]
        for idx, sent in chosen:
            lines.append(f"- {sent.rstrip('.')}. [{idx}]")
        return "\n".join(lines)

    def _directory_answer(self, prompt: str, directory: list[tuple[int, str, str]]) -> str:
        q = prompt.lower()
        parts: list[str] = []
        for idx, _title, body in directory:
            fields = dict(
                (k.strip().lower(), v.strip()) for k, _, v in (line.partition(":") for line in body.splitlines()) if v
            )
            name = fields.get("name", "This employee")
            if re.search(r"salar|band|compensation|pay|ctc|earn", q):
                if "salary band" in fields:
                    parts.append(
                        f"{name} ({fields.get('title', '')}, {fields.get('department', '')}) is in salary band "
                        f"{fields['salary band']}, range {fields.get('salary range', 'not listed')} (synthetic test data). [{idx}]"
                    )
                else:
                    parts.append(f"Compensation details for {name} are not available to your role. [{idx}]")
            elif re.search(r"contact|email|phone|reach|call", q):
                parts.append(f"You can reach {name} at {fields.get('work email', '')} or {fields.get('phone', '')}. [{idx}]")
            else:
                parts.append(
                    f"{name} is a {fields.get('title', 'team member')} in {fields.get('department', 'NovaCorp')}, "
                    f"based in {fields.get('location', 'an unlisted location')}. "
                    f"Contact: {fields.get('work email', '')}, {fields.get('phone', '')}. [{idx}]"
                )
        return "\n".join(parts)
