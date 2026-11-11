"""Compliance Evidence Center API."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import Conflict, NotFound
from app.models import AuditEvent, ComplianceReport, ReportSchedule, User
from app.schemas.compliance import ReportDetail, ReportOut, ReportRequest, ScheduleOut, ScheduleRequest
from app.schemas.misc import AuditEventOut
from app.services import audit, evidence
from app.workers import tasks

router = APIRouter(prefix="/compliance", tags=["compliance evidence"])
can_read = require_permission("compliance:read")
can_write = require_permission("compliance:write")


def _ready(r: ComplianceReport) -> ComplianceReport:
    if r.status not in ("READY", "EXPIRED") or not r.content:
        raise Conflict(f"Report is {r.status.lower()}")
    return r


@router.get("/options")
def report_options(_: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    return evidence.options(db)


@router.post("/reports", response_model=ReportOut, status_code=202)
def generate_report(body: ReportRequest, background: BackgroundTasks, user: User = Depends(can_write), db: Session = Depends(get_db)):
    filters = evidence.parse_filters(body.model_dump())
    report = evidence.create_report(db, body.report_type, filters, user, body.retention_days, title=body.title)
    background.add_task(tasks.generate_report, report.id)
    return report


@router.get("/reports", response_model=list[ReportOut])
def list_reports(report_type: str | None = None, status: str | None = None, include_withdrawn: bool = False,
                 _: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    stmt = select(ComplianceReport).order_by(ComplianceReport.id.desc()).limit(200)
    if report_type:
        stmt = stmt.where(ComplianceReport.report_type == report_type)
    if status:
        stmt = stmt.where(ComplianceReport.status == status.upper())
    if not include_withdrawn:
        stmt = stmt.where(ComplianceReport.deleted_at.is_(None))
    return [evidence.refresh_expiry(db, r) for r in db.scalars(stmt)]


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report(report_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)):
    return evidence.get_report(db, report_id, include_withdrawn=True)


@router.get("/reports/{report_id}/preview")
def preview(report_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    r = _ready(evidence.get_report(db, report_id))
    return {"integrity": evidence.integrity_block(r), "content": r.content}


@router.get("/reports/{report_id}/verify")
def verify(report_id: int, user: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    r = evidence.get_report(db, report_id, include_withdrawn=True)
    result = evidence.verify(db, r)
    audit.record(db, "compliance.report_verified", **audit.actor_fields(user), commit=True,
                 details={"report_id": r.id, "reproducible": result["reproducible"]})
    return result


@router.get("/reports/{report_id}/export")
def export(report_id: int, format: str = Query("markdown", pattern="^(markdown|json|html)$"), user: User = Depends(can_read),
           db: Session = Depends(get_db)):
    r = _ready(evidence.get_report(db, report_id))
    audit.record(db, "compliance.report_exported", **audit.actor_fields(user), content_hash=r.content_hash, commit=True,
                 details={"report_id": r.id, "format": format})
    name = f"trustshield-{r.report_type}-{r.id}-v{r.version}"
    disposition = {"Content-Disposition": f'attachment; filename="{name}.{ {"markdown": "md", "json": "json", "html": "html"}[format] }"'}
    if format == "json":
        return JSONResponse(evidence.export_json(r), headers=disposition)
    if format == "html":
        return HTMLResponse(evidence.export_html(r), headers=disposition)
    return PlainTextResponse(evidence.export_markdown(r), media_type="text/markdown; charset=utf-8", headers=disposition)


@router.post("/reports/{report_id}/schedule", response_model=ScheduleOut, status_code=201)
def schedule(report_id: int, body: ScheduleRequest, user: User = Depends(can_write), db: Session = Depends(get_db)):
    return evidence.create_schedule(db, _ready(evidence.get_report(db, report_id)), user, body.cadence, body.retention_days)


@router.delete("/reports/{report_id}", status_code=204)
def withdraw(report_id: int, user: User = Depends(can_write), db: Session = Depends(get_db)) -> None:
    r = evidence.get_report(db, report_id)
    if r.status == "GENERATING":
        raise Conflict("Wait for the report to finish generating")
    evidence.withdraw(db, r, user)


@router.get("/evidence/{report_id}/sources")
def sources(report_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
            _: User = Depends(require_permission("compliance:read")), db: Session = Depends(get_db)) -> dict:
    r = evidence.get_report(db, report_id, include_withdrawn=True)
    ids = r.source_event_ids or []
    chunk = ids[(page - 1) * page_size: page * page_size]
    rows = {e.id: e for e in db.scalars(select(AuditEvent).where(AuditEvent.id.in_(chunk or [-1])))}
    items = [AuditEventOut.model_validate(rows[i]).model_dump(mode="json") for i in chunk if i in rows]
    return {"report_id": r.id, "total": len(ids), "page": page, "page_size": page_size, "items": items}


@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(_: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    return list(db.scalars(select(ReportSchedule).order_by(ReportSchedule.id.desc())))


@router.delete("/schedules/{schedule_id}", status_code=204)
def cancel_schedule(schedule_id: int, user: User = Depends(can_write), db: Session = Depends(get_db)) -> None:
    s = db.get(ReportSchedule, schedule_id)
    if s is None:
        raise NotFound("Schedule")
    s.is_active = False
    audit.record(db, "compliance.schedule_cancelled", **audit.actor_fields(user), details={"schedule_id": s.id}, commit=True)


@router.post("/schedules/run-due")
def run_due(user: User = Depends(can_write), db: Session = Depends(get_db)) -> dict:
    """Run any schedules that are due now (the background loop does this automatically every minute)."""
    reports = evidence.run_due_schedules(db)
    return {"generated": [r.id for r in reports]}


@router.get("/summary")
def summary(_: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    counts = dict(db.execute(select(ComplianceReport.status, func.count()).where(ComplianceReport.deleted_at.is_(None))
                             .group_by(ComplianceReport.status)).all())
    active = db.scalar(select(func.count()).select_from(ReportSchedule).where(ReportSchedule.is_active.is_(True))) or 0
    if not counts and not active:
        return {"by_status": {}, "active_schedules": 0}
    return {"by_status": counts, "active_schedules": active}


