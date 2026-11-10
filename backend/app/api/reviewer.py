from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import User
from app.schemas.misc import ReviewCaseDetail, ReviewCaseOut, ReviewDecision, ReviewEdit
from app.services import reviews

router = APIRouter(prefix="/reviewer", tags=["reviewer"])
can_read = require_permission("reviews:read")
can_act = require_permission("reviews:act")


def _detail(db: Session, case) -> dict:  # type: ignore[no-untyped-def]
    data = ReviewCaseDetail.model_validate(case).model_dump()
    requester = db.get(User, case.requester_id) if case.requester_id else None
    resolver = db.get(User, case.resolved_by) if case.resolved_by else None
    data["requester_department"] = requester.department if requester else None
    data["resolved_by_email"] = resolver.email if resolver else None
    return data


@router.get("/cases", response_model=list[ReviewCaseOut])
def list_cases(
    status: str | None = Query(None, description="open | resolved | PENDING | ESCALATED | APPROVED | EDITED | REJECTED"),
    priority: str | None = None,
    origin: str | None = None,
    q: str | None = Query(None, max_length=200),
    _: User = Depends(can_read),
    db: Session = Depends(get_db),
) -> list:
    return reviews.list_cases(db, status=status, priority=priority, origin=origin, q=q)


@router.get("/cases/{case_id}", response_model=ReviewCaseDetail)
def get_case(case_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    return _detail(db, reviews.get_case(db, case_id))


@router.post("/cases/{case_id}/approve", response_model=ReviewCaseDetail)
def approve(case_id: int, body: ReviewDecision, user: User = Depends(can_act), db: Session = Depends(get_db)) -> dict:
    return _detail(db, reviews.approve(db, reviews.get_case(db, case_id), user, body.note))


@router.post("/cases/{case_id}/reject", response_model=ReviewCaseDetail)
def reject(case_id: int, body: ReviewDecision, user: User = Depends(can_act), db: Session = Depends(get_db)) -> dict:
    return _detail(db, reviews.reject(db, reviews.get_case(db, case_id), user, body.note))


@router.post("/cases/{case_id}/edit", response_model=ReviewCaseDetail)
def edit(case_id: int, body: ReviewEdit, user: User = Depends(can_act), db: Session = Depends(get_db)) -> dict:
    return _detail(db, reviews.edit(db, reviews.get_case(db, case_id), user, body.edited_response, body.note))


@router.post("/cases/{case_id}/escalate", response_model=ReviewCaseDetail)
def escalate(case_id: int, body: ReviewDecision, user: User = Depends(can_act), db: Session = Depends(get_db)) -> dict:
    return _detail(db, reviews.escalate(db, reviews.get_case(db, case_id), user, body.note))


@router.post("/cases/{case_id}/notes", response_model=ReviewCaseDetail)
def add_note(case_id: int, body: ReviewDecision, user: User = Depends(can_act), db: Session = Depends(get_db)) -> dict:
    return _detail(db, reviews.add_note(db, reviews.get_case(db, case_id), user, body.note))
