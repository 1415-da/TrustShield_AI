"""Background work executed with FastAPI BackgroundTasks (no Celery/Redis needed at MVP scale).

Each task opens its own session because the request-scoped session is closed once the response is sent.
"""

from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.models import ComplianceReport, Document, TestRun
from app.services import documents, evaluation, evidence

log = logging.getLogger("trustshield.workers")


def reindex_document(document_id: int) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            documents.index_document(db, doc)
        except Exception:  # pragma: no cover
            log.exception("indexing failed", extra={"document_id": document_id})
            db.rollback()
            doc = db.get(Document, document_id)
            if doc:
                doc.status = "failed"
                db.commit()


def run_test_suite(run_id: int, case_ids: list[int] | None = None) -> None:
    with SessionLocal() as db:
        run = db.get(TestRun, run_id)
        if run is not None:
            evaluation.execute_run(db, run, case_ids)


def generate_report(report_id: int) -> None:
    with SessionLocal() as db:
        report = db.get(ComplianceReport, report_id)
        if report is not None and report.status == "GENERATING":
            evidence.generate(db, report)


def run_due_schedules() -> int:
    with SessionLocal() as db:
        return len(evidence.run_due_schedules(db))
