#!/usr/bin/env python3
"""Generate reports/TEST_REPORT.md from pytest JUnit XML, Playwright JSON, and a fresh guardrail evaluation.

The guardrail evaluation runs every seeded scenario through the real gateway against an in-memory
SQLite database with the offline mock model, so the numbers are reproducible on any machine.
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def backend_summary() -> str:
    path = REPORTS / "backend-junit.xml"
    if not path.exists():
        return "_Backend JUnit report not found — run `scripts/run_tests.sh` first._\n"
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    total, failures, errors, skipped = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    by_file: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for case in suite.iter("testcase"):
        mod = case.get("classname", "").split(".")[-1]
        ok = case.find("failure") is None and case.find("error") is None
        by_file[mod][0] += 1
        by_file[mod][1] += int(ok)
    lines = [f"**{total - failures - errors - skipped} / {total} passed** · {failures} failures · {errors} errors · {skipped} skipped\n",
             "| Module | Passed |", "|---|---|"]
    lines += [f"| `{m}` | {p}/{t} |" for m, (t, p) in sorted(by_file.items())]
    return "\n".join(lines) + "\n"


def e2e_summary() -> str:
    path = REPORTS / "e2e-results.json"
    if not path.exists():
        return "_Playwright results not found — run `scripts/run_tests.sh --e2e` with the stack running._\n"
    data = json.loads(path.read_text())
    rows = []

    def walk(suite: dict) -> None:
        for spec in suite.get("specs", []):
            status = "passed" if all(t.get("status") == "expected" for t in spec.get("tests", [])) else "failed"
            rows.append((spec["title"], status))
        for s in suite.get("suites", []):
            walk(s)

    for s in data.get("suites", []):
        walk(s)
    passed = sum(1 for _, st in rows if st == "passed")
    return "\n".join([f"**{passed} / {len(rows)} passed**\n", "| Scenario | Result |", "|---|---|"] +
                     [f"| {t} | {'✅' if st == 'passed' else '❌'} {st} |" for t, st in rows]) + "\n"


def guardrail_summary() -> str:
    os.environ["DATABASE_URL"] = "sqlite://"
    sys.path.insert(0, str(ROOT / "backend"))
    os.chdir(ROOT / "backend")
    import app.models  # noqa: F401
    from app.core.database import Base, SessionLocal, engine
    from app.models import TestRun
    from app.seed.loader import seed_reference
    from app.services.evaluation import execute_run

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db, "report-only-password")
        run = TestRun(status="running")
        db.add(run)
        db.commit()
        run = execute_run(db, run)
        s = run.summary
        lines = [
            f"**{run.passed} / {run.total} scenarios passed** ({s['pass_rate']:.0%})\n",
            f"- False positives: **{run.false_positives}** of {s['safe_cases']} safe cases ({s['false_positive_rate']:.1%})",
            f"- False negatives: **{run.false_negatives}** of {s['restrictive_cases']} restrictive cases ({s['false_negative_rate']:.1%})",
            f"- Ambiguous-by-design cases (excluded from FP/FN): {s['either_cases']}",
            f"- Mean gateway latency per scenario (mock model): {s['avg_latency_ms']} ms\n",
            "| Category | Passed |", "|---|---|",
        ]
        lines += [f"| {k} | {v['passed']}/{v['total']} |" for k, v in sorted(s["by_category"].items())]
        failures = [r for r in run.results if not r.passed]
        if failures:
            lines += ["", "**Failures**", ""] + [f"- case {r.test_case_id}: {r.failure_reason}" for r in failures]
    return "\n".join(lines) + "\n"


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = f"""# TrustShield AI — Test Report

Generated {now}. All data is synthetic; the evaluation uses the offline mock model.

## 1. Backend (pytest)

{backend_summary()}
## 2. Guardrail evaluation (seeded scenarios)

{guardrail_summary()}
> Scores are measured on the labelled demo suite only. They are not production performance claims.

## 3. Frontend end-to-end (Playwright)

{e2e_summary()}"""
    out = REPORTS / "TEST_REPORT.md"
    out.write_text(body)
    print(f"[report] wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
