"""Row-level tenant isolation at the ORM layer.

Every model that inherits `TenantMixin` is automatically:
  * filtered on read to the session's organization (`with_loader_criteria` on every ORM SELECT), and
  * stamped on insert with that organization (`before_flush`).

The organization lives in `session.info["org_id"]`. Request handlers set it from the signed-in user (see
`app.core.deps`). Request-scoped sessions (`get_db`) are marked `org_required`: touching tenant data before a
workspace is bound raises `TenantScopeError` instead of silently using the default workspace. Scripts and workers
that never bind one act within the default workspace. The few system lookups that must
span organizations (sign-in by email, API-key lookup) opt out explicitly with `ALL_ORGS`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.models.organization import DEFAULT_ORG_ID, Organization, TenantMixin

ALL_ORGS = {"all_orgs": True}


class TenantScopeError(RuntimeError):
    """Raised when a request touches workspace data before its workspace is known — never fall back silently."""


def org_id(db: Session) -> int:
    oid = db.info.get("org_id")
    if oid:
        return int(oid)
    if db.info.get("org_required"):
        raise TenantScopeError("This request has no workspace scope")
    # Scripts, workers and tests that never bind a workspace operate on the default (platform) workspace.
    return DEFAULT_ORG_ID


def use_org(db: Session, organization_id: int) -> None:
    """Bind a session to an organization. Clears cached org details so names are re-read."""
    if db.info.get("org_id") != organization_id:
        db.info.pop("org", None)
    db.info["org_id"] = organization_id


def current_org(db: Session) -> Organization | None:
    cached = db.info.get("org")
    if cached is not None and cached.id == org_id(db):
        return cached
    org = db.get(Organization, org_id(db))
    db.info["org"] = org
    return org


def org_name(db: Session | None) -> str:
    """Display name for user-facing copy ("…checked by Acme's compliance team")."""
    if db is None:
        return "your organization"
    org = current_org(db)
    return org.name if org else "your organization"


@event.listens_for(Session, "do_orm_execute")
def _scope_reads(state: ORMExecuteState) -> None:
    if not state.is_select or state.is_column_load or state.is_relationship_load:
        return
    if state.execution_options.get("all_orgs"):
        return
    if not any(issubclass(m.class_, TenantMixin) for m in state.all_mappers):
        return  # platform tables (roles, sessions, organizations) are not workspace data
    oid = org_id(state.session)
    state.statement = state.statement.options(
        with_loader_criteria(TenantMixin, lambda cls: cls.organization_id == oid, include_aliases=True)
    )


@event.listens_for(Session, "before_flush")
def _stamp_inserts(session: Session, *_: Any) -> None:
    pending = [o for o in session.new if isinstance(o, TenantMixin) and getattr(o, "organization_id", None) is None]
    if not pending:
        return
    oid = org_id(session)
    for obj in pending:
        obj.organization_id = oid


def localize(db: Session | None, value: Any) -> Any:
    """Swap the default workspace's name in user-facing copy for the current organization's name."""
    name = org_name(db)
    if name == "NovaCorp":
        return value
    if isinstance(value, str):
        possessive = f"{name}'" if name.endswith("s") else f"{name}'s"
        return value.replace("NovaCorp's", possessive).replace("NovaCorp", name)
    if isinstance(value, dict):
        return {k: localize(db, v) for k, v in value.items()}
    if isinstance(value, list):
        return [localize(db, v) for v in value]
    return value
