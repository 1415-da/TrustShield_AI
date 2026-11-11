"""Employee directory (developer note: seeded rows are synthetic) used to (a) detect prompts that target named employees and (b) supply
role-appropriate directory facts to the model. Salary bands are only included for callers holding the
`data:compensation` scope; test national IDs are never included."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmployeeRecord

DIRECTORY_TITLE = "NovaCorp Employee Directory"


def directory_names(db: Session) -> list[str]:
    return list(db.scalars(select(EmployeeRecord.full_name)))


def lookup(db: Session, names: list[str]) -> list[EmployeeRecord]:
    if not names:
        return []
    records = db.scalars(select(EmployeeRecord).where(EmployeeRecord.full_name.in_(names))).all()
    return list(records)


def describe(record: EmployeeRecord, permissions: set[str]) -> str:
    lines = [
        f"Name: {record.full_name}",
        f"Title: {record.title}",
        f"Department: {record.department}",
        f"Location: {record.location}",
        f"Work email: {record.work_email}",
        f"Phone: {record.phone}",
    ]
    if "data:compensation" in permissions:
        lines += [f"Salary band: {record.salary_band}", f"Salary range: {record.salary_range}"]
    lines.append("Record type: employee directory entry")
    return "\n".join(lines)
