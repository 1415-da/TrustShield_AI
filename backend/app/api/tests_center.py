from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import Conflict, NotFound
from app.models import TestCase, TestRun, User
from app.schemas.misc import TestCaseIn, TestCaseOut, TestResultOut, TestRunOut, TestRunRequest
from app.services import audit
from app.workers import tasks

router = APIRouter(prefix="/admin/tests", tags=["test center"])
can_run = require_permission("tests:run")


@router.get("", response_model=list[TestCaseOut])
def list_tests(_: User = Depends(can_run), db: Session = Depends(get_db)) -> list:
    return list(db.scalars(select(TestCase).order_by(TestCase.code)))


@router.post("", response_model=TestCaseOut, status_code=201)
def create_test(body: TestCaseIn, user: User = Depends(can_run), db: Session = Depends(get_db)):
    if db.scalar(select(TestCase).where(TestCase.code == body.code)):
        raise Conflict("A test case with this code already exists")
    tc = TestCase(**body.model_dump())
    db.add(tc)
    audit.record(db, "test_case.created", **audit.actor_fields(user), details={"code": body.code, "category": body.category})
    db.commit()
    return tc


@router.get("/runs", response_model=list[TestRunOut])
def list_runs(_: User = Depends(can_run), db: Session = Depends(get_db)) -> list:
    return list(db.scalars(select(TestRun).order_by(TestRun.id.desc()).limit(20)))


@router.post("/run", response_model=TestRunOut, status_code=202)
def run_tests(background: BackgroundTasks, body: TestRunRequest | None = None, user: User = Depends(can_run),
              db: Session = Depends(get_db)):
    run = TestRun(status="running", triggered_by=user.id)
    db.add(run)
    db.flush()
    audit.record(db, "test_run.started", **audit.actor_fields(user), details={"run_id": run.id})
    db.commit()
    background.add_task(tasks.run_test_suite, run.id, body.case_ids if body else None)
    return run


@router.get("/runs/{run_id}", response_model=TestRunOut)
def get_run(run_id: int, _: User = Depends(can_run), db: Session = Depends(get_db)):
    run = db.get(TestRun, run_id)
    if run is None:
        raise NotFound("Test run")
    return run


@router.get("/runs/{run_id}/results", response_model=list[TestResultOut])
def run_results(run_id: int, _: User = Depends(can_run), db: Session = Depends(get_db)) -> list:
    run = db.get(TestRun, run_id)
    if run is None:
        raise NotFound("Test run")
    cases = {c.id: c for c in db.scalars(select(TestCase))}
    out = []
    for r in run.results:
        tc = cases.get(r.test_case_id)
        row = TestResultOut.model_validate(r).model_dump()
        if tc:
            row.update(code=tc.code, name=tc.name, category=tc.category, role_key=tc.role_key, prompt=tc.prompt,
                       expected_input_actions=tc.expected_input_actions, expected_output_actions=tc.expected_output_actions)
        out.append(row)
    return out
