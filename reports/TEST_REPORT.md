# TrustShield AI — Test Report

Generated 2026-11-10 18:16 UTC. All data is synthetic; the evaluation uses the offline mock model.

## 1. Backend (pytest)

**120 / 120 passed** · 0 failures · 0 errors · 0 skipped

| Module | Passed |
|---|---|
| `test_api` | 31/31 |
| `test_classifiers` | 8/8 |
| `test_evaluation` | 49/49 |
| `test_gateway` | 12/12 |
| `test_pii` | 10/10 |
| `test_rules_grounding` | 10/10 |

## 2. Guardrail evaluation (seeded scenarios)

**49 / 49 scenarios passed** (100%)

- False positives: **0** of 12 safe cases (0.0%)
- False negatives: **0** of 31 restrictive cases (0.0%)
- Ambiguous-by-design cases (excluded from FP/FN): 6
- Mean gateway latency per scenario (mock model): 71.8 ms

| Category | Passed |
|---|---|
| bank_account | 2/2 |
| credentials | 2/2 |
| credit_card | 2/2 |
| escalation | 2/2 |
| grounded_answer | 4/4 |
| indirect_injection | 1/1 |
| legal_review | 1/1 |
| low_confidence | 2/2 |
| output_pii | 2/2 |
| pii_detection | 4/4 |
| prompt_injection | 5/5 |
| redaction_quality | 4/4 |
| role_permission | 3/3 |
| safe_policy | 8/8 |
| salary_authorized | 2/2 |
| salary_unauthorized | 4/4 |
| unsupported_answer | 1/1 |

> Scores are measured on the labelled demo suite only. They are not production performance claims.

## 3. Frontend end-to-end (Playwright)

**8 / 8 passed**

| Scenario | Result |
|---|---|
| landing page presents the product and links to the live demo | ✅ passed |
| employee gets a verified, cited answer to a safe policy question | ✅ passed |
| salary request is blocked with a plain-language explanation | ✅ passed |
| personal data in a prompt is masked before storage and the model | ✅ passed |
| employees cannot open the governance console | ✅ passed |
| admin creates an inactive policy and tests it immediately in the simulator | ✅ passed |
| reviewer approves a held answer and the employee receives it | ✅ passed |
| auditor can verify the hash-chained audit log | ✅ passed |
