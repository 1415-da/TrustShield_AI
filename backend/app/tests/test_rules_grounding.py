"""Rule evaluator semantics, decision precedence, and grounding risk signals."""

from app.guardrails.decision import decide_input, decide_output
from app.guardrails.grounding import assess_grounding
from app.guardrails.pii import get_pii_detector
from app.guardrails.rules import EvaluationContext, FieldAnalysis, PolicySnapshot, RuleSnapshot, evaluate_policies
from app.guardrails.topics import classify_topics
from app.guardrails.types import InputAction, OutputAction, RuleMatch


def policy(*rules: RuleSnapshot, action="BLOCK", roles=()) -> PolicySnapshot:
    return PolicySnapshot(1, "P", "cat", action, "HIGH", 0.5, "msg", tuple(roles), True, tuple(rules))


def ctx(text: str, perms=frozenset(), roles=frozenset({"employee"}), field="user_input", confidence=None) -> EvaluationContext:
    ents = get_pii_detector().analyze(text)
    fa = FieldAnalysis(text, ents, classify_topics(text, ents, ["Ravi Sharma"]), confidence)
    return EvaluationContext(set(roles), set(perms), {field: fa})


def rule(rule_type: str, **kw) -> RuleSnapshot:
    return RuleSnapshot(id=1, name=rule_type, rule_type=rule_type, match_field=kw.pop("match_field", "user_input"), **kw)


def m(action: str, severity="HIGH") -> RuleMatch:
    return RuleMatch(1, "P", 1, "r", "regex", "user_input", action, severity, "cat", 1.0, "")


def test_regex_and_keyword_rules():
    p = policy(rule("regex", pattern=r"acme\s+corp"), rule("keyword", keywords=["poach"]))
    assert len(evaluate_policies([p], ctx("Can we poach staff from Acme Corp?"), "user_input")) == 2
    assert evaluate_policies([p], ctx("Hello there"), "user_input") == []


def test_pii_entity_rule_reports_masked_evidence():
    p = policy(rule("pii_entity", entity_types=("EMAIL_ADDRESS",)))
    hits = evaluate_policies([p], ctx("mail jane.doe@example.test"), "user_input")
    assert hits and "jane.doe" not in hits[0].evidence


def test_role_permission_rule_respects_scope():
    p = policy(rule("role_permission", topic="salary", required_permission="data:compensation", threshold=0.6))
    assert evaluate_policies([p], ctx("Show Ravi Sharma's salary"), "user_input")
    assert not evaluate_policies([p], ctx("Show Ravi Sharma's salary", perms={"data:compensation"}), "user_input")


def test_applicable_roles_filter():
    p = policy(rule("keyword", keywords=["refund"]), roles=("finance_analyst",))
    assert not evaluate_policies([p], ctx("refund please"), "user_input")
    assert evaluate_policies([p], ctx("refund please", roles={"finance_analyst"}), "user_input")


def test_confidence_threshold_rule():
    p = policy(rule("confidence_threshold", match_field="llm_output", threshold=0.4))
    assert evaluate_policies([p], ctx("answer", field="llm_output", confidence=0.2), "llm_output")
    assert not evaluate_policies([p], ctx("answer", field="llm_output", confidence=0.8), "llm_output")


def test_input_precedence():
    assert decide_input([m("REDACT"), m("BLOCK"), m("ESCALATE")]) == InputAction.ESCALATE
    assert decide_input([m("REDACT"), m("REVIEW")]) == InputAction.REVIEW
    assert decide_input([]) == InputAction.ALLOW


def test_output_precedence_and_allow_means_warning():
    assert decide_output([m("ALLOW")]) == OutputAction.SHOW_WITH_WARNING
    assert decide_output([m("REDACT"), m("REVIEW")]) == OutputAction.SEND_TO_REVIEW
    assert decide_output([m("REDACT")], forced=[OutputAction.BLOCK]) == OutputAction.BLOCK


EVIDENCE = ["Refunds below USD 5,000 are approved by the Finance Operations lead. Refunds of USD 5,000 or more require the Finance Controller."]


def test_grounded_answer_scores_high():
    g = assess_grounding("Who approves vendor refunds?",
                         "Refunds below USD 5,000 are approved by the Finance Operations lead. [1]", EVIDENCE, 0.6)
    assert g.groundedness >= 0.6 and g.confidence >= 0.6


def test_unsupported_answer_scores_low():
    g = assess_grounding("What is the policy for Martian vendors?",
                         "Martian vendors probably get refunds within 900 days, I think.", EVIDENCE, 0.2)
    assert g.confidence < 0.45
    assert "900" in g.unsupported_numbers and "martian" in g.unsupported_terms


def test_no_evidence_is_low_confidence_and_labelled():
    g = assess_grounding("Anything?", "Some answer here that is long enough to count.", [], 0.0)
    assert g.confidence < 0.3
    assert "not a guarantee" in g.public()["label"]
