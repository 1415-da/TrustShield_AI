"""Policy lifecycle: drafts, review, approval, activation, deactivation, rollback, archive.

State machine (per version)::

    DRAFT ──submit──► IN_REVIEW ──approve──► APPROVED ──activate──► ACTIVE ──deactivate──► INACTIVE ──► ARCHIVED
      ▲                  │  │                                        │ (superseded on next activation → ARCHIVED)
      └──── edit ◄── CHANGES_REQUESTED                                │
      └──── edit ◄── REJECTED ◄───────────────────────────────────────┘ (INACTIVE can be re-activated)

Rules enforced here:
* Only the ACTIVE version is enforced (also guaranteed by a partial unique index).
* Snapshots are immutable once a version leaves DRAFT; editing an ACTIVE policy creates a new DRAFT.
* Separation of duties: whoever authored or submitted a version cannot approve it.
* Rollback creates a *new* version copied from a previously approved one; old versions are never mutated.
* Every transition writes a policy_audit_event and a hash-chained global audit event.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.guardrails.rules import PolicySnapshot
from app.models import Policy, PolicyApproval, PolicyAuditEvent, PolicyComment, PolicyException, PolicyVersion, User
from app.models.base import utcnow
from app.models.policy import EDITABLE_STATUSES
from app.services import audit

DEFINITION_FIELDS = ("name", "description", "risk_category", "sensitive_data_type", "owner", "review_cadence_days",
                     "applicable_roles", "profiles", "action", "severity", "threshold", "user_message",
                     "effective_from", "effective_to")
RULE_FIELDS = ("key", "name", "rule_type", "match_field", "pattern", "keywords", "entity_types", "topic",
               "required_permission", "threshold", "action", "severity", "applies_to_roles", "is_active")
WORKING = ("DRAFT", "CHANGES_REQUESTED", "REJECTED", "IN_REVIEW", "APPROVED")

TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"IN_REVIEW", "ARCHIVED"},
    "IN_REVIEW": {"APPROVED", "CHANGES_REQUESTED", "REJECTED"},
    "CHANGES_REQUESTED": {"DRAFT", "ARCHIVED"},
    "REJECTED": {"DRAFT", "ARCHIVED"},
    "APPROVED": {"ACTIVE", "ARCHIVED"},
    "ACTIVE": {"INACTIVE", "ARCHIVED"},
    "INACTIVE": {"ACTIVE", "ARCHIVED"},
    "ARCHIVED": set(),
}


# --------------------------------------------------------------------------- definitions
def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


def normalize_definition(data: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Canonical snapshot dict. Rule `key`s are kept stable across versions so diffs line up."""
    base = dict(previous or {})
    for f in DEFINITION_FIELDS:
        if f in data and data[f] is not None:
            base[f] = _iso(data[f])
    base.setdefault("description", "")
    base.setdefault("sensitive_data_type", "none")
    base.setdefault("owner", "")
    base.setdefault("review_cadence_days", 180)
    base.setdefault("applicable_roles", [])
    base.setdefault("profiles", [])
    base.setdefault("severity", "MEDIUM")
    base.setdefault("threshold", 0.5)
    base.setdefault("user_message", "")
    base.setdefault("effective_from", None)
    base.setdefault("effective_to", None)
    if data.get("rules") is not None:
        rules = []
        for r in data["rules"]:
            rule = {f: r.get(f) for f in RULE_FIELDS}
            rule["key"] = rule.get("key") or uuid.uuid4().hex[:8]
            rule["name"] = rule.get("name") or rule["rule_type"]
            rule["keywords"] = list(rule.get("keywords") or [])
            rule["entity_types"] = list(rule.get("entity_types") or [])
            rule["applies_to_roles"] = list(rule.get("applies_to_roles") or [])
            rule["match_field"] = rule.get("match_field") or "user_input"
            rule["is_active"] = True if rule.get("is_active") is None else bool(rule["is_active"])
            rules.append(rule)
        base["rules"] = rules
    if not base.get("rules"):
        raise BadRequest("A policy needs at least one rule")
    for required in ("name", "risk_category", "action"):
        if not base.get(required):
            raise BadRequest(f"Missing {required}")
    return base


def definition_hash(definition: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(definition, sort_keys=True, default=str).encode()).hexdigest()


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)


# --------------------------------------------------------------------------- queries
def get_policy(db: Session, policy_id: int, include_archived: bool = False) -> Policy:
    policy = db.get(Policy, policy_id)
    if policy is None or (policy.is_archived and not include_archived):
        raise NotFound("Policy")
    return policy


def list_policies(db: Session) -> list[Policy]:
    return list(db.scalars(select(Policy).where(Policy.is_archived.is_(False)).order_by(Policy.risk_category, Policy.name)))


def get_version(db: Session, policy: Policy, version_id: int) -> PolicyVersion:
    v = db.get(PolicyVersion, version_id)
    if v is None or v.policy_id != policy.id:
        raise NotFound("Policy version")
    return v


def active_version(policy: Policy) -> PolicyVersion | None:
    return next((v for v in policy.versions if v.status == "ACTIVE"), None)


def working_version(policy: Policy) -> PolicyVersion | None:
    """The single in-flight version (draft, in review, changes requested, rejected, or approved-not-active)."""
    candidates = [v for v in policy.versions if v.status in WORKING]
    return max(candidates, key=lambda v: v.version) if candidates else None


def head_version(policy: Policy) -> PolicyVersion | None:
    return active_version(policy) or (policy.versions[-1] if policy.versions else None)


def family_status(policy: Policy) -> str:
    if policy.is_archived:
        return "ARCHIVED"
    if active_version(policy):
        return "ACTIVE"
    w = working_version(policy)
    if w:
        return w.status
    return "INACTIVE" if any(v.status == "INACTIVE" for v in policy.versions) else "ARCHIVED"


def is_effective(v: PolicyVersion, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return (v.effective_from is None or v.effective_from <= now) and (v.effective_to is None or v.effective_to > now)


def active_snapshots(db: Session, include: list[PolicySnapshot] | None = None, now: datetime | None = None) -> list[PolicySnapshot]:
    """Enforced policies: ACTIVE versions whose effective window covers `now`. `include` overrides by family id."""
    rows = db.scalars(
        select(PolicyVersion).join(Policy, Policy.id == PolicyVersion.policy_id)
        .where(PolicyVersion.status == "ACTIVE", Policy.is_archived.is_(False))
    ).all()
    snaps = [PolicySnapshot.from_version(v) for v in rows if is_effective(v, now)]
    for extra in include or []:
        snaps = [s for s in snaps if s.id != extra.id] + [extra]
    return snaps


# --------------------------------------------------------------------------- audit
def _record(db: Session, policy: Policy, version: PolicyVersion | None, event_type: str, user: User | None,
            from_status: str | None = None, to_status: str | None = None, note: str = "", details: dict | None = None,
            ) -> PolicyAuditEvent:
    db.flush()
    ev = audit.record(
        db, f"policy.{event_type}", **audit.actor_fields(user), policy_ids=[policy.id],
        details={"policy": policy.name, "version": version.version if version else None, "from": from_status,
                 "to": to_status, "note": note[:500], **(details or {})},
    )
    row = PolicyAuditEvent(
        policy_id=policy.id, version_id=version.id if version else None, version_number=version.version if version else None,
        event_type=event_type, from_status=from_status, to_status=to_status, actor_id=user.id if user else None,
        actor_email=user.email if user else None, actor_role=user.primary_role if user else None, note=note,
        details=details or {}, audit_event_id=ev.id, created_at=ev.created_at,
    )
    db.add(row)
    return row


def _transition(db: Session, policy: Policy, v: PolicyVersion, to: str, user: User | None, event_type: str, note: str = "",
                details: dict | None = None) -> None:
    if to not in TRANSITIONS[v.status]:
        raise Conflict(f"Version v{v.version} is {v.status}; it cannot move to {to}")
    previous = v.status
    v.status = to
    v.updated_at = utcnow()
    _record(db, policy, v, event_type, user, previous, to, note, details)


# --------------------------------------------------------------------------- authoring
def _new_version(db: Session, policy: Policy, definition: dict, user: User | None, summary: str,
                 status: str = "DRAFT", based_on: PolicyVersion | None = None) -> PolicyVersion:
    policy.latest_version += 1
    v = PolicyVersion(
        policy_id=policy.id, version=policy.latest_version, status=status, snapshot=definition,
        snapshot_hash=definition_hash(definition), change_summary=summary[:500],
        based_on_version_id=based_on.id if based_on else None,
        effective_from=_parse_dt(definition.get("effective_from")), effective_to=_parse_dt(definition.get("effective_to")),
        created_by=user.id if user else None, created_by_email=user.email if user else "system",
    )
    policy.versions.append(v)
    db.flush()
    return v


def _sync_family(policy: Policy, definition: dict) -> None:
    policy.risk_category = definition["risk_category"]
    policy.owner = definition.get("owner") or ""
    policy.review_cadence_days = int(definition.get("review_cadence_days") or 180)


def create_policy(db: Session, data: dict[str, Any], user: User | None, summary: str = "Initial draft") -> Policy:
    if db.scalar(select(Policy).where(Policy.name == data.get("name"))):
        raise Conflict("A policy with this name already exists")
    definition = normalize_definition(data)
    policy = Policy(name=definition["name"], risk_category=definition["risk_category"], created_by=user.id if user else None)
    _sync_family(policy, definition)
    db.add(policy)
    db.flush()
    v = _new_version(db, policy, definition, user, summary)
    _record(db, policy, v, "created", user, None, "DRAFT", summary)
    db.commit()
    return policy


def save_draft(db: Session, policy: Policy, data: dict[str, Any], user: User | None, summary: str = "") -> PolicyVersion:
    """Edit the open draft, or start a new draft from the current head. Never touches the ACTIVE version."""
    w = working_version(policy)
    if w and w.status in ("IN_REVIEW", "APPROVED"):
        raise Conflict(f"v{w.version} is {w.status.replace('_', ' ').lower()}; finish or withdraw it before editing")
    if "name" in data and data["name"] and data["name"] != policy.name:
        if db.scalar(select(Policy).where(Policy.name == data["name"], Policy.id != policy.id)):
            raise Conflict("A policy with this name already exists")
    if w and w.status in EDITABLE_STATUSES:
        definition = normalize_definition(data, w.snapshot)
        if w.status != "DRAFT":
            _transition(db, policy, w, "DRAFT", user, "reopened", "Draft reopened for edits")
        w.snapshot = definition
        w.snapshot_hash = definition_hash(definition)
        w.effective_from, w.effective_to = _parse_dt(definition.get("effective_from")), _parse_dt(definition.get("effective_to"))
        w.change_summary = (summary or w.change_summary)[:500]
        _record(db, policy, w, "draft_saved", user, "DRAFT", "DRAFT", summary)
        version = w
    else:
        head = head_version(policy)
        definition = normalize_definition(data, head.snapshot if head else None)
        version = _new_version(db, policy, definition, user, summary or "New draft", based_on=head)
        _record(db, policy, version, "draft_created", user, None, "DRAFT", summary,
                {"based_on": head.version if head else None})
    policy.name = definition["name"]
    _sync_family(policy, definition)
    db.commit()
    return version


def submit_for_review(db: Session, policy: Policy, user: User, note: str = "") -> PolicyApproval:
    w = working_version(policy)
    if w is None or w.status != "DRAFT":
        raise Conflict("There is no draft to submit")
    w.submitted_by, w.submitted_at = user.id, utcnow()
    _transition(db, policy, w, "IN_REVIEW", user, "submitted", note)
    approval = PolicyApproval(policy_id=policy.id, version_id=w.id, requested_by=user.id, requested_by_email=user.email,
                              request_note=note)
    db.add(approval)
    db.commit()
    return approval


def pending_approval(db: Session, version: PolicyVersion) -> PolicyApproval | None:
    return db.scalar(select(PolicyApproval).where(PolicyApproval.version_id == version.id, PolicyApproval.status == "PENDING"))


def decide(db: Session, policy: Policy, user: User, decision: str, note: str = "") -> PolicyVersion:
    """decision ∈ APPROVED | CHANGES_REQUESTED | REJECTED."""
    w = working_version(policy)
    if w is None or w.status != "IN_REVIEW":
        raise Conflict("No version of this policy is awaiting review")
    if user.id in {w.created_by, w.submitted_by}:
        raise Forbidden("Separation of duties: you authored or submitted this version, so another approver must review it")
    if decision in ("CHANGES_REQUESTED", "REJECTED") and not note.strip():
        raise BadRequest("Explain what needs to change")
    approval = pending_approval(db, w)
    if approval:
        approval.status, approval.decided_by, approval.decided_by_email = decision, user.id, user.email
        approval.decision_note, approval.decided_at = note, utcnow()
    if decision == "APPROVED":
        w.approved_by, w.approved_by_email, w.approved_at = user.id, user.email, utcnow()
    event = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes_requested", "REJECTED": "rejected"}[decision]
    _transition(db, policy, w, decision, user, event, note)
    db.commit()
    return w


def activate(db: Session, policy: Policy, user: User, version_id: int | None = None, note: str = "") -> PolicyVersion:
    if version_id:
        target = get_version(db, policy, version_id)
    else:
        target = next((v for v in reversed(policy.versions) if v.status == "APPROVED"), None)
        if target is None:
            raise Conflict("No approved version is waiting for activation")
    if target.status == "ACTIVE":
        return target
    if target.status not in ("APPROVED", "INACTIVE") or not target.approved_by:
        raise Conflict(f"v{target.version} is {target.status}; only approved versions can be activated")
    current = active_version(policy)
    if current:
        current.deactivated_at = utcnow()
        _transition(db, policy, current, "ARCHIVED", user, "superseded", f"Superseded by v{target.version}")
        db.flush()  # release the one-active index before activating the new version
    target.activated_by, target.activated_by_email, target.activated_at = user.id, user.email, utcnow()
    target.deactivated_at = None
    _transition(db, policy, target, "ACTIVE", user, "activated", note,
                {"scheduled": bool(target.effective_from and target.effective_from > utcnow())})
    policy.active_version_id = target.id
    db.commit()
    return target


def deactivate(db: Session, policy: Policy, user: User, note: str = "") -> PolicyVersion:
    current = active_version(policy)
    if current is None:
        raise Conflict("This policy has no active version")
    current.deactivated_at = utcnow()
    _transition(db, policy, current, "INACTIVE", user, "deactivated", note)
    policy.active_version_id = None
    db.commit()
    return current


def rollback(db: Session, policy: Policy, user: User, version_id: int, note: str = "", activate_now: bool = False) -> PolicyVersion:
    source = get_version(db, policy, version_id)
    if not source.approved_by:
        raise Conflict("You can only roll back to a version that was previously approved")
    w = working_version(policy)
    if w and w.status in ("IN_REVIEW", "APPROVED"):
        raise Conflict(f"v{w.version} is {w.status.replace('_', ' ').lower()}; resolve it before rolling back")
    if w and w.status in EDITABLE_STATUSES:
        _transition(db, policy, w, "ARCHIVED", user, "discarded", f"Discarded by rollback to v{source.version}")
    definition = dict(source.snapshot)
    v = _new_version(db, policy, definition, user, f"Rollback to v{source.version}" + (f": {note}" if note else ""),
                     status="APPROVED", based_on=source)
    # Approval carries over from the version being restored; the rollback actor is recorded separately.
    v.approved_by, v.approved_by_email, v.approved_at = source.approved_by, source.approved_by_email, utcnow()
    _record(db, policy, v, "rolled_back", user, None, "APPROVED", note, {"restored_from": source.version})
    policy.name = definition["name"]
    _sync_family(policy, definition)
    db.commit()
    if activate_now:
        activate(db, policy, user, v.id, f"Activated rollback to v{source.version}")
    return v


def archive_policy(db: Session, policy: Policy, user: User | None, note: str = "") -> None:
    for v in policy.versions:
        if v.status == "ACTIVE":
            v.deactivated_at = utcnow()
            _transition(db, policy, v, "INACTIVE", user, "deactivated", "Policy archived")
        if v.status == "IN_REVIEW":
            _transition(db, policy, v, "REJECTED", user, "withdrawn", "Policy archived")
            approval = pending_approval(db, v)
            if approval:
                approval.status = "WITHDRAWN"
        if v.status != "ARCHIVED":
            _transition(db, policy, v, "ARCHIVED", user, "archived", note or "Policy archived")
    policy.is_archived = True
    policy.active_version_id = None
    db.commit()


def add_comment(db: Session, policy: Policy, user: User, body: str, version_id: int | None = None) -> PolicyComment:
    if not body.strip():
        raise BadRequest("Comment cannot be empty")
    if version_id:
        get_version(db, policy, version_id)
    c = PolicyComment(policy_id=policy.id, version_id=version_id, author_id=user.id, author_email=user.email, body=body.strip())
    db.add(c)
    _record(db, policy, None, "commented", user, note=body.strip()[:500], details={"version_id": version_id})
    db.commit()
    return c


def comments(db: Session, policy_id: int) -> list[PolicyComment]:
    return list(db.scalars(select(PolicyComment).where(PolicyComment.policy_id == policy_id).order_by(PolicyComment.id)))


def audit_history(db: Session, policy_id: int) -> list[PolicyAuditEvent]:
    return list(db.scalars(select(PolicyAuditEvent).where(PolicyAuditEvent.policy_id == policy_id).order_by(PolicyAuditEvent.id.desc())))


def approvals(db: Session, status: str | None = "PENDING") -> list[PolicyApproval]:
    stmt = select(PolicyApproval).order_by(PolicyApproval.requested_at.desc())
    if status:
        stmt = stmt.where(PolicyApproval.status == status)
    return list(db.scalars(stmt))


# --------------------------------------------------------------------------- diff
COMPARED_FIELDS = ("name", "description", "risk_category", "sensitive_data_type", "owner", "review_cadence_days",
                   "applicable_roles", "profiles", "action", "severity", "threshold", "user_message",
                   "effective_from", "effective_to")
RULE_COMPARED = ("name", "rule_type", "match_field", "pattern", "keywords", "entity_types", "topic",
                 "required_permission", "threshold", "action", "severity", "applies_to_roles", "is_active")


def diff_definitions(old: dict | None, new: dict) -> dict[str, Any]:
    """Structured diff: changed policy fields plus added / removed / changed rules (matched by stable key)."""
    old = old or {}
    fields = [{"field": f, "before": old.get(f), "after": new.get(f)} for f in COMPARED_FIELDS if old.get(f) != new.get(f)]
    old_rules = {r.get("key") or f"idx{i}": r for i, r in enumerate(old.get("rules") or [])}
    new_rules = {r.get("key") or f"idx{i}": r for i, r in enumerate(new.get("rules") or [])}
    added = [new_rules[k] for k in new_rules if k not in old_rules]
    removed = [old_rules[k] for k in old_rules if k not in new_rules]
    changed = []
    for k in new_rules:
        if k in old_rules:
            changes = [{"field": f, "before": old_rules[k].get(f), "after": new_rules[k].get(f)}
                       for f in RULE_COMPARED if old_rules[k].get(f) != new_rules[k].get(f)]
            if changes:
                changed.append({"key": k, "name": new_rules[k].get("name"), "changes": changes})
    return {"fields": fields, "rules_added": added, "rules_removed": removed, "rules_changed": changed,
            "has_changes": bool(fields or added or removed or changed)}


# --------------------------------------------------------------------------- exceptions
def active_exceptions(db: Session, now: datetime | None = None) -> list[PolicyException]:
    now = now or utcnow()
    return list(db.scalars(select(PolicyException).where(
        PolicyException.status == "APPROVED", PolicyException.starts_at <= now, PolicyException.expires_at > now)))


def exempt_policy_ids(db: Session, *, email: str, roles: set[str], department: str, now: datetime | None = None) -> set[int]:
    out = set()
    for e in active_exceptions(db, now):
        if (e.subject_type == "user" and e.subject.lower() == email.lower()) or \
           (e.subject_type == "role" and e.subject in roles) or \
           (e.subject_type == "department" and department and e.subject.lower() == department.lower()):
            out.add(e.policy_id)
    return out


def request_exception(db: Session, policy: Policy, user: User, data: dict[str, Any]) -> PolicyException:
    if data["subject_type"] not in ("user", "role", "department"):
        raise BadRequest("subject_type must be user, role, or department")
    expires = _parse_dt(data["expires_at"])
    starts = _parse_dt(data.get("starts_at")) or utcnow()
    if not expires or expires <= starts:
        raise BadRequest("An exception must expire after it starts")
    if (expires - starts).days > 365:
        raise BadRequest("Exceptions can last at most 365 days")
    ex = PolicyException(policy_id=policy.id, subject_type=data["subject_type"], subject=data["subject"],
                         justification=data["justification"], requested_by=user.id, requested_by_email=user.email,
                         starts_at=starts, expires_at=expires)
    db.add(ex)
    db.flush()
    _record(db, policy, None, "exception_requested", user, note=data["justification"][:500],
            details={"exception_id": ex.id, "subject_type": ex.subject_type, "subject": ex.subject})
    db.commit()
    return ex


def decide_exception(db: Session, ex: PolicyException, user: User, decision: str, note: str = "") -> PolicyException:
    policy = get_policy(db, ex.policy_id, include_archived=True)
    if decision in ("APPROVED", "REJECTED"):
        if ex.status != "REQUESTED":
            raise Conflict(f"Exception is already {ex.status.lower()}")
        if user.id == ex.requested_by:
            raise Forbidden("Separation of duties: you requested this exception")
    elif decision == "REVOKED":
        if ex.status != "APPROVED":
            raise Conflict("Only approved exceptions can be revoked")
        ex.revoked_at = utcnow()
    else:
        raise BadRequest("Unknown decision")
    ex.status, ex.decided_by, ex.decided_by_email, ex.decision_note = decision, user.id, user.email, note
    if decision != "REVOKED":
        ex.decided_at = utcnow()
    _record(db, policy, None, f"exception_{decision.lower()}", user, note=note[:500],
            details={"exception_id": ex.id, "subject_type": ex.subject_type, "subject": ex.subject})
    db.commit()
    return ex


def list_exceptions(db: Session) -> list[PolicyException]:
    return list(db.scalars(select(PolicyException).order_by(PolicyException.created_at.desc())))

