"""Policy CRUD with automatic version snapshots and audit events."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.guardrails.rules import PolicySnapshot
from app.models import Policy, PolicyRule, PolicyVersion, User
from app.services import audit

RULE_FIELDS = ("name", "rule_type", "match_field", "pattern", "keywords", "entity_types", "topic", "required_permission",
               "threshold", "action", "severity", "applies_to_roles", "is_active")
POLICY_FIELDS = ("name", "description", "risk_category", "sensitive_data_type", "applicable_roles", "action", "severity",
                 "threshold", "user_message", "is_active")


def snapshot_dict(policy: Policy) -> dict[str, Any]:
    data = {f: getattr(policy, f) for f in POLICY_FIELDS}
    data["version"] = policy.version
    data["rules"] = [{"id": r.id, **{f: getattr(r, f) for f in RULE_FIELDS}} for r in policy.rules]
    return data


def get_policy(db: Session, policy_id: int) -> Policy:
    policy = db.get(Policy, policy_id)
    if policy is None or policy.is_archived:
        raise NotFound("Policy")
    return policy


def list_policies(db: Session) -> list[Policy]:
    return list(db.scalars(select(Policy).where(Policy.is_archived.is_(False)).order_by(Policy.risk_category, Policy.name)))


def active_snapshots(db: Session, include: list[PolicySnapshot] | None = None) -> list[PolicySnapshot]:
    policies = db.scalars(select(Policy).where(Policy.is_active.is_(True), Policy.is_archived.is_(False))).all()
    snaps = [PolicySnapshot.from_model(p) for p in policies]
    for extra in include or []:
        snaps = [s for s in snaps if s.id != extra.id] + [extra]
    return snaps


def _apply_rules(policy: Policy, rules: list[dict[str, Any]]) -> None:
    policy.rules.clear()
    for r in rules:
        policy.rules.append(PolicyRule(**{k: v for k, v in r.items() if k in RULE_FIELDS}))


def _version(db: Session, policy: Policy, user: User | None, summary: str) -> None:
    db.flush()
    db.add(PolicyVersion(policy_id=policy.id, version=policy.version, snapshot=snapshot_dict(policy),
                         change_summary=summary, changed_by=user.id if user else None))


def create_policy(db: Session, data: dict[str, Any], user: User | None) -> Policy:
    if db.scalar(select(Policy).where(Policy.name == data["name"])):
        raise Conflict("A policy with this name already exists")
    rules = data.pop("rules", [])
    if not rules:
        raise BadRequest("A policy needs at least one rule")
    policy = Policy(**{k: v for k, v in data.items() if k in POLICY_FIELDS}, created_by=user.id if user else None, version=1)
    _apply_rules(policy, rules)
    db.add(policy)
    _version(db, policy, user, "Created")
    audit.record(db, "policy.created", **audit.actor_fields(user), policy_ids=[policy.id],
                 details={"name": policy.name, "version": 1, "action": policy.action, "active": policy.is_active})
    db.commit()
    return policy


def update_policy(db: Session, policy: Policy, data: dict[str, Any], user: User | None, summary: str = "") -> Policy:
    changed = []
    for key, value in data.items():
        if key == "rules" and value is not None:
            _apply_rules(policy, value)
            changed.append("rules")
        elif key in POLICY_FIELDS and value is not None and getattr(policy, key) != value:
            setattr(policy, key, value)
            changed.append(key)
    if not changed:
        return policy
    if "name" in changed and db.scalar(select(Policy).where(Policy.name == policy.name, Policy.id != policy.id)):
        raise Conflict("A policy with this name already exists")
    policy.version += 1
    _version(db, policy, user, summary or f"Updated {', '.join(changed)}")
    audit.record(db, "policy.updated", **audit.actor_fields(user), policy_ids=[policy.id],
                 details={"name": policy.name, "version": policy.version, "changed": changed})
    db.commit()
    return policy


def set_active(db: Session, policy: Policy, active: bool, user: User | None) -> Policy:
    if policy.is_active == active:
        return policy
    policy.is_active = active
    policy.version += 1
    _version(db, policy, user, "Activated" if active else "Deactivated")
    audit.record(db, "policy.activated" if active else "policy.deactivated", **audit.actor_fields(user),
                 policy_ids=[policy.id], details={"name": policy.name, "version": policy.version})
    db.commit()
    return policy


def archive_policy(db: Session, policy: Policy, user: User | None) -> None:
    """Soft delete: versions and audit history remain queryable."""
    policy.is_archived = True
    policy.is_active = False
    policy.version += 1
    _version(db, policy, user, "Archived")
    audit.record(db, "policy.archived", **audit.actor_fields(user), policy_ids=[policy.id],
                 details={"name": policy.name, "version": policy.version})
    db.commit()


def versions(db: Session, policy_id: int) -> list[PolicyVersion]:
    return list(db.scalars(select(PolicyVersion).where(PolicyVersion.policy_id == policy_id).order_by(PolicyVersion.version.desc())))
