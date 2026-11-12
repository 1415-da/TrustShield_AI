"""Background work executed with FastAPI BackgroundTasks (no Celery/Redis needed at MVP scale).

Each task opens its own session because the request-scoped session is closed once the response is sent.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.tenancy import ALL_ORGS, use_org
from app.models import ComplianceReport, Document, Organization, TestRun
from app.services import documents, evaluation, evidence

log = logging.getLogger("trustshield.workers")


def reindex_document(document_id: int) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, document_id, execution_options=ALL_ORGS)
        if doc is None:
            return
        use_org(db, doc.organization_id)
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
        run = db.get(TestRun, run_id, execution_options=ALL_ORGS)
        if run is not None:
            use_org(db, run.organization_id)
            evaluation.execute_run(db, run, case_ids)


def generate_report(report_id: int) -> None:
    with SessionLocal() as db:
        report = db.get(ComplianceReport, report_id, execution_options=ALL_ORGS)
        if report is not None and report.status == "GENERATING":
            use_org(db, report.organization_id)
            evidence.generate(db, report)


def run_due_schedules() -> int:
    """Run due report schedules for every organization, each in its own scoped session."""
    with SessionLocal() as db:
        org_ids = list(db.scalars(select(Organization.id)))
    total = 0
    for oid in org_ids:
        with SessionLocal() as db:
            use_org(db, oid)
            total += len(evidence.run_due_schedules(db))
    return total
