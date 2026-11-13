"""Agent action governance.

    request ─► input guardrails (injection / PII) ─► classify ─► agent + permission check ─► action policies ─► risk
            ─► EXECUTE │ REQUIRE_APPROVAL │ SEND_TO_REVIEW │ ESCALATE │ BLOCK │ NEEDS_INFO
            ─► (approval by the named role, never the requester) ─► controlled executor ─► audit

Invariants (all covered by tests):
* Nothing executes unless the decision was EXECUTE or a person holding the required approver role approved it.
* Permissions are re-checked immediately before execution.
* At most one successful execution per action (partial unique index) and per-user request idempotency keys.
* Every state transition writes an action_audit_event mirrored into the hash-chained audit log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.guardrails.pii import get_pii_detector
from app.guardrails.pipeline import GuardrailEngine
from app.models import (ActionApproval, ActionAuditEvent, ActionExecution, ActionIdempotencyKey, ActionPolicy, ActionType, Agent,
                        AgentAction, Conversation, Message, User)
from app.models.base import utcnow
from app.services import audit, directory, gateway, policies
from app.services.action_executors import EXPENSE_CLAIMS, VENDOR_INVOICES, ActionContext, ExecutorError, get_executor

DECISION_ORDER = ["BLOCK", "ESCALATE", "REQUIRE_APPROVAL", "SEND_TO_REVIEW", "EXECUTE"]
ESCALATION_RISK = 0.9
OPEN_STATUSES = ("PENDING_APPROVAL", "IN_REVIEW", "ESCALATED", "NEEDS_INFO")
# Employee-facing approver names; they use the canonical role names from app.core.permissions.
ROLE_NAMES = {"finance_head": "the Finance Head", "people_manager": "a People Manager", "hr_manager": "an HR Manager",
              "security_admin": "a Security Admin", "compliance_reviewer": "a Compliance Reviewer"}
ETA = {"finance_head": "Within 1 business day", "people_manager": "Within 1 business day", "hr_manager": "Within 1 business day",
       "security_admin": "Within 4 hours", "compliance_reviewer": "Within 8 hours"}
CATEGORY_RISK = {"READ": 0.05, "SENSITIVE_READ": 0.45, "CREATE": 0.15, "UPDATE": 0.35, "FINANCIAL_ACTION": 0.5,
                 "COMMUNICATION": 0.4, "DESTRUCTIVE_ACTION": 0.75, "ADMIN_ACTION": 0.7}
CATEGORY_DEFAULT = {"READ": ("EXECUTE", None), "SENSITIVE_READ": ("REQUIRE_APPROVAL", "hr_manager"), "CREATE": ("EXECUTE", None),
                    "UPDATE": ("REQUIRE_APPROVAL", "people_manager"), "FINANCIAL_ACTION": ("REQUIRE_APPROVAL", "finance_head"),
                    "COMMUNICATION": ("SEND_TO_REVIEW", "compliance_reviewer"), "DESTRUCTIVE_ACTION": ("REQUIRE_APPROVAL", "security_admin"),
                    "ADMIN_ACTION": ("REQUIRE_APPROVAL", "security_admin")}

# --------------------------------------------------------------------------- registry
ACTION_TYPES: list[dict[str, Any]] = [
    {"key": "leave.view_own", "name": "View own leave balance", "category": "READ", "target_system": "HR system", "executor": "leave_balance",
     "description": "Read the requester's own leave balance."},
    {"key": "salary.view", "name": "View a salary band", "category": "SENSITIVE_READ", "target_system": "HR system", "executor": "salary_band",
     "required_permission": "data:compensation", "description": "Look up an employee's salary band."},
    {"key": "ticket.create", "name": "Create a ticket", "category": "CREATE", "target_system": "Issue tracker", "executor": "ticket",
     "description": "Open a ticket (e.g. a security issue) in the issue tracker."},
    {"key": "leave.update", "name": "Update a leave balance", "category": "UPDATE", "target_system": "HR system", "executor": "leave_update",
     "required_permission": "actions:hr", "description": "Change an employee's leave balance."},
    {"key": "salary.update", "name": "Change compensation", "category": "UPDATE", "target_system": "HR system", "executor": "salary_update",
     "required_permission": "actions:hr", "description": "Change an employee's salary or band."},
    {"key": "expense.reimburse", "name": "Approve an expense reimbursement", "category": "FINANCIAL_ACTION", "target_system": "Expense portal",
     "executor": "expense_reimbursement", "required_permission": "actions:finance", "description": "Approve and pay a submitted expense claim."},
    {"key": "vendor.refund", "name": "Issue a vendor refund", "category": "FINANCIAL_ACTION", "target_system": "Finance Operations portal",
     "executor": "vendor_refund", "required_permission": "actions:finance", "description": "Record a refund against a vendor invoice."},
    {"key": "notify.send", "name": "Send a notification", "category": "COMMUNICATION", "target_system": "Email / messaging", "executor": "notification",
     "description": "Send an email or message, internally or to an external party."},
    {"key": "access.revoke", "name": "Revoke access", "category": "DESTRUCTIVE_ACTION", "target_system": "Identity provider",
     "executor": "access_revoke", "required_permission": "actions:it", "description": "Remove a user's access to a system."},
    {"key": "record.delete", "name": "Delete a record", "category": "DESTRUCTIVE_ACTION", "target_system": "Records system",
     "executor": "record_delete", "required_permission": "actions:it", "description": "Delete (soft-delete) a business record."},
    {"key": "permission.change", "name": "Change permissions or policy", "category": "ADMIN_ACTION", "target_system": "TrustShield / IAM",
     "executor": "admin_change", "required_permission": "users:manage", "description": "Open a change request for roles, permissions or policy."},
]

AGENTS: list[dict[str, Any]] = [
    {"key": "finance-agent", "name": "Finance Operations Agent", "owner_team": "Finance", "description": "Reimbursements, vendor refunds, and vendor notices.",
     "allowed_action_types": ["expense.reimburse", "vendor.refund", "notify.send"]},
    {"key": "people-agent", "name": "People Operations Agent", "owner_team": "HR", "description": "Leave balances and compensation changes.",
     "allowed_action_types": ["leave.view_own", "leave.update", "salary.view", "salary.update"]},
    {"key": "it-agent", "name": "IT Service Agent", "owner_team": "IT", "description": "Tickets, access changes, and record clean-up.",
     "allowed_action_types": ["ticket.create", "access.revoke", "record.delete", "notify.send"]},
    {"key": "admin-agent", "name": "Governance Change Agent", "owner_team": "AI Platform", "status": "active",
     "description": "Opens change requests for permissions and policy. Never edits configuration directly.",
     "allowed_action_types": ["permission.change"]},
]

DEFAULT_POLICIES: list[dict[str, Any]] = [
    {"name": "Read actions run automatically", "category": "READ", "decision": "EXECUTE", "priority": 10,
     "description": "Looking up your own information is safe to automate."},
    {"name": "Authorised roles may read sensitive records", "category": "SENSITIVE_READ", "decision": "EXECUTE", "priority": 10,
     "description": "Role permission is enforced first; roles without the data scope are blocked before this rule applies."},
    {"name": "Tickets and requests are created automatically", "category": "CREATE", "decision": "EXECUTE", "priority": 10},
    {"name": "Record updates need manager approval", "category": "UPDATE", "decision": "REQUIRE_APPROVAL", "approver_role": "people_manager", "priority": 20},
    {"name": "Salary changes need HR Manager approval", "action_type": "salary.update", "decision": "REQUIRE_APPROVAL", "approver_role": "hr_manager", "priority": 40,
     "description": "Any action involving employee salary data requires an HR Manager."},
    {"name": "Reimbursements under INR 5,000 auto-approve for Finance", "action_type": "expense.reimburse", "decision": "EXECUTE", "priority": 30,
     "conditions": {"amount_lt": 5000, "requester_roles": ["finance_analyst", "finance_head"]}},
    {"name": "Reimbursements INR 5,000–50,000 need manager approval", "action_type": "expense.reimburse", "decision": "REQUIRE_APPROVAL",
     "approver_role": "people_manager", "priority": 30, "conditions": {"amount_gte": 5000, "amount_lte": 50000}},
    {"name": "Reimbursements above INR 50,000 need Finance Head approval", "action_type": "expense.reimburse", "decision": "REQUIRE_APPROVAL",
     "approver_role": "finance_head", "priority": 35, "conditions": {"amount_gt": 50000}},
    {"name": "Vendor refunds up to INR 10,000 run for Finance", "action_type": "vendor.refund", "decision": "EXECUTE", "priority": 30,
     "conditions": {"amount_lte": 10000, "requester_roles": ["finance_analyst", "finance_head"]}},
    {"name": "Vendor refunds above INR 10,000 need Finance Head approval", "action_type": "vendor.refund", "decision": "REQUIRE_APPROVAL",
     "approver_role": "finance_head", "priority": 35, "conditions": {"amount_gt": 10000}},
    {"name": "External communication is reviewed by Compliance", "category": "COMMUNICATION", "decision": "SEND_TO_REVIEW",
     "approver_role": "compliance_reviewer", "priority": 30, "conditions": {"external": True}},
    {"name": "Internal notifications send automatically", "category": "COMMUNICATION", "decision": "EXECUTE", "priority": 10, "conditions": {"external": False}},
    {"name": "Deletions and access revocations need Security Admin approval", "category": "DESTRUCTIVE_ACTION", "decision": "REQUIRE_APPROVAL",
     "approver_role": "security_admin", "priority": 40},
    {"name": "Admin actions need Security Admin approval", "category": "ADMIN_ACTION", "decision": "REQUIRE_APPROVAL",
     "approver_role": "security_admin", "priority": 40, "description": "Admin-only (users:manage) and always approved by a second person."},
]


def ensure_registry(db: Session) -> int:
    """Create missing agents, action types and default action policies (idempotent). Returns rows added."""
    added = 0
    have = {t.key for t in db.scalars(select(ActionType))}
    for t in ACTION_TYPES:
        if t["key"] not in have:
            db.add(ActionType(**t))
            added += 1
    have = {a.key for a in db.scalars(select(Agent))}
    for a in AGENTS:
        if a["key"] not in have:
            db.add(Agent(**a))
            added += 1
    have = {p.name for p in db.scalars(select(ActionPolicy))}
    for p in DEFAULT_POLICIES:
        if p["name"] not in have:
            db.add(ActionPolicy(**{"conditions": {}, **p}))
            added += 1
    db.commit()
    return added


# --------------------------------------------------------------------------- classification
@dataclass
class Classified:
    action_type: str | None
    params: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    target_record: str = ""
    amount: float | None = None
    external: bool = False
    missing: list[str] = field(default_factory=list)


AMOUNT_RE = re.compile(r"(?:₹|\bINR\s?|\bRs\.?\s?)(\d[\d,]*(?:\.\d+)?)\s*(k|K|lakh|L)?|(\d[\d,]*(?:\.\d+)?)\s*(?:INR|rupees)", re.I)


def _amount(text: str) -> float | None:
    m = AMOUNT_RE.search(text)
    if not m:
        return None
    raw, unit = (m.group(1) or m.group(3)).replace(",", ""), (m.group(2) or "").lower()
    value = float(raw)
    return value * 1000 if unit == "k" else value * 100000 if unit in ("lakh", "l") else value


def _person(db: Session, text: str) -> str | None:
    for name in directory.directory_names(db):
        first = name.split()[0]
        if name.lower() in text.lower() or re.search(rf"\b{re.escape(first)}\b", text):
            return name
    return None


def classify(db: Session, text: str) -> Classified:
    """Deterministic, explainable intent parser for the supported action catalogue."""
    t = text.strip()
    low = t.lower()
    person = _person(db, t)
    if re.search(r"\b(revoke|remove|disable|cut off)\b.{0,40}\baccess\b", low):
        who = person or (re.search(r"\bfor\s+([\w .@-]{2,60}?)(?:\s+(?:from|to|on)\b|$|[.,])", t) or [None, None])[1] or ""
        return Classified("access.revoke", {"subject": who.strip() or "unspecified user", "change": "revoke access"},
                          f"Revoke access for {who.strip() or 'a user'}", who.strip(), missing=[] if who.strip() else ["who should lose access"])
    if re.search(r"\b(delete|purge|erase|wipe)\b", low):
        what = re.sub(r"^(please\s+)?(delete|purge|erase|wipe)\s+", "", t, flags=re.I).strip(" .")
        return Classified("record.delete", {"subject": what[:120], "change": "delete"}, f"Delete {what[:120]}", what[:120])
    if re.search(r"\b(change|grant|give|update|edit|add)\b.{0,40}\b(permission|permissions|role|roles|policy|policies|admin rights)\b", low):
        return Classified("permission.change", {"subject": person or "workspace", "change": t[:300]}, f"Change request: {t[:120]}", "Roles and policies")
    inv = re.search(r"\bINV-\d{3,6}\b", t, re.I)
    if re.search(r"\brefund\b", low) and not re.search(r"\b(send|email|notify|message)\b", low):
        if not inv:
            return Classified("vendor.refund", {}, "Issue a vendor refund", "", missing=["the vendor invoice number (INV-…)"])
        inv_id = inv.group(0).upper()
        record = VENDOR_INVOICES.get(inv_id)
        amount = _amount(t) or (record["amount"] if record else None)
        missing = [] if record else [f"a valid invoice number ({inv_id} was not found)"]
        return Classified("vendor.refund", {"invoice_id": inv_id, "amount": amount}, f"Refund vendor invoice {inv_id}" +
                          (f" ({record['vendor']})" if record else ""), inv_id, amount, missing=missing)
    if re.search(r"\b(reimburse|reimbursement|expense claim|expense)\b", low) and re.search(r"\b(approve|pay|reimburse|process|release)\b", low):
        claim_id = (re.search(r"\bEXP-\d{3,6}\b", t, re.I) or [None])[0]
        claim_id = claim_id.upper() if claim_id else next((k for k, c in EXPENSE_CLAIMS.items() if person and c["employee"] == person), None)
        if not claim_id:
            return Classified("expense.reimburse", {}, "Approve an expense reimbursement", "", missing=["which expense claim (EXP-… or the employee's name)"])
        claim = EXPENSE_CLAIMS.get(claim_id)
        if claim is None:
            return Classified("expense.reimburse", {}, "Approve an expense reimbursement", claim_id, missing=[f"a valid claim ({claim_id} was not found)"])
        return Classified("expense.reimburse", {"claim_id": claim_id, "amount": claim["amount"]},
                          f"Approve {claim['employee']}'s expense claim {claim_id} — {claim['description']}", claim_id, claim["amount"])
    # An explicit ticket-creation intent wins over words like "email" in the ticket's subject.
    if re.search(r"\b(ticket|jira|issue|incident)\b", low) and re.search(r"\b(create|open|raise|file|log)\b", low):
        about = re.sub(r"^(please\s+)?(create|open|raise|file|log)\s+(a|an)?\s*(jira\s+)?(ticket|issue)\s*(for|about)?\s*", "", t, flags=re.I).strip(" .") or t
        return Classified("ticket.create", {"summary": about[:300], "priority": "High" if "security" in low else "Medium"},
                          f"Create a ticket: {about[:120]}", "Issue tracker")
    if re.search(r"\b(send|email|notify|message|tell)\b", low):
        external = bool(re.search(r"\b(vendor|supplier|customer|client|external|partner)\b", low) or re.search(r"@(?!novacorp\.)", low))
        recipient = "vendor" if "vendor" in low else (person or ("external party" if external else "internal team"))
        return Classified("notify.send", {"recipient": recipient, "message": t[:500], "external": external},
                          f"Send a message to {recipient}", recipient, external=external)
    if re.search(r"\b(leave|vacation|time[- ]off)\b", low) and re.search(r"\b(update|set|change|adjust|add|correct)\b", low):
        days = re.search(r"(\d+(?:\.\d+)?)\s*days?", low)
        who = person or ("the employee" if "employee" in low else None)
        missing = [] if (person and days) else (["which employee"] if not person else []) + (["the new balance in days"] if not days else [])
        return Classified("leave.update", {"employee": person or "", "days": float(days.group(1)) if days else None},
                          f"Update {who or 'an employee'}'s leave balance" + (f" to {days.group(1)} days" if days else ""), who or "", missing=missing)
    if re.search(r"\b(salary|compensation|pay band|band)\b", low) and re.search(r"\b(raise|increase|change|update|set|promote|adjust)\b", low):
        return Classified("salary.update", {"subject": person or "", "change": t[:200]}, f"Change compensation for {person or 'an employee'}",
                          person or "", _amount(t), missing=[] if person else ["which employee"])
    if re.search(r"\b(salary|pay band|salary band)\b", low):
        return Classified("salary.view", {"subject": person or ""}, f"Look up {person or 'an employee'}'s salary band", person or "")
    if re.search(r"\b(my|own)\b.{0,20}\b(leave|vacation)\b.{0,20}\bbalance\b", low):
        return Classified("leave.view_own", {"subject": "self"}, "Look up your leave balance", "Your leave record")
    return Classified(None, summary="Unrecognised action", missing=["a supported action (refunds, reimbursements, leave, tickets, notifications)"])


# --------------------------------------------------------------------------- policy evaluation & risk
def _conditions_match(cond: dict[str, Any], amount: float | None, roles: set[str], external: bool) -> bool:
    for key, op in (("amount_gt", lambda a, v: a > v), ("amount_gte", lambda a, v: a >= v),
                    ("amount_lt", lambda a, v: a < v), ("amount_lte", lambda a, v: a <= v)):
        if key in cond and cond[key] is not None:
            if amount is None or not op(amount, float(cond[key])):
                return False
    if cond.get("requester_roles") and not set(cond["requester_roles"]) & roles:
        return False
    if "external" in cond and cond["external"] is not None and bool(cond["external"]) != external:
        return False
    return True


def evaluate_policies(db: Session, action_type: ActionType, amount: float | None, roles: set[str], external: bool) -> tuple[str, str | None, list[dict]]:
    rows = [p for p in db.scalars(select(ActionPolicy).where(ActionPolicy.is_active.is_(True)))
            if (p.action_type == action_type.key or (p.action_type is None and p.category == action_type.category))
            and _conditions_match(p.conditions or {}, amount, roles, external)]
    if not rows:
        decision, role = CATEGORY_DEFAULT[action_type.category]
        return decision, role, [{"policy_id": None, "name": f"Default for {action_type.category.replace('_', ' ').lower()}", "decision": decision,
                                 "approver_role": role, "reason": "No configured action policy matched; the category default applies."}]
    rows.sort(key=lambda p: (DECISION_ORDER.index(p.decision), -p.priority))
    top = rows[0]
    basis = [{"policy_id": p.id, "name": p.name, "decision": p.decision, "approver_role": p.approver_role, "reason": p.description or ""} for p in rows]
    return top.decision, top.approver_role, basis


BULK_RE = re.compile(r"\b(all|every|entire|everyone|bulk|mass)\b", re.I)


def risk_score(category: str, amount: float | None, external: bool, injection: float, text: str) -> float:
    score = CATEGORY_RISK.get(category, 0.5)
    if amount:
        score += min(0.3, amount / 400000)
    if external:
        score += 0.1
    if BULK_RE.search(text):
        score += 0.25
    score += injection * 0.5
    return round(min(1.0, score), 3)


# --------------------------------------------------------------------------- audit & messages
def _event(db: Session, action: AgentAction, event_type: str, user: User | None, frm: str | None, to: str | None, note: str = "",
           details: dict | None = None) -> None:
    db.flush()
    ev = audit.record(db, f"agent_action.{event_type}", **audit.actor_fields(user), final_action=to,
                      details={"action_id": action.id, "action_type": action.action_type, "from": frm, "to": to,
                               "amount": action.amount, "note": note[:500], **(details or {})})
    db.add(ActionAuditEvent(action_id=action.id, event_type=event_type, from_status=frm, to_status=to,
                            actor_id=user.id if user else None, actor_email=user.email if user else "system",
                            actor_role=user.primary_role if user else None, note=note, details=details or {},
                            audit_event_id=ev.id, created_at=ev.created_at))


def _set_status(db: Session, action: AgentAction, to: str, user: User | None, event_type: str, note: str = "", details: dict | None = None) -> None:
    frm = action.status
    action.status = to
    action.updated_at = utcnow()
    _event(db, action, event_type, user, frm, to, note, details)
    _sync_message(db, action)


def employee_view(action: AgentAction) -> dict[str, Any]:
    """Plain-language status for the requester."""
    role = ROLE_NAMES.get(action.required_approver_role or "", action.required_approver_role or "an approver")
    headline = {
        "EXECUTED": "This action was completed.",
        "PENDING_APPROVAL": f"This action requires approval from {role}.",
        "APPROVED": "This action was approved and is being completed.",
        "EXECUTING": "This action is being completed.",
        "IN_REVIEW": "This action is under review.",
        "ESCALATED": "This action is under review by the security team.",
        "NEEDS_INFO": "This action needs additional information.",
        "BLOCKED": "This action was blocked by policy.",
        "REJECTED": "This action was not approved.",
        "FAILED": "This action could not be completed. Nothing was changed.",
        "COMPENSATED": "This action was reversed.",
    }.get(action.status, action.status)
    eta = "Completed" if action.status == "EXECUTED" else ETA.get(action.required_approver_role or "", "—") if action.status in OPEN_STATUSES else "—"
    reason = (action.policy_basis or [{}])[0].get("reason") or (action.policy_basis or [{}])[0].get("name", "")
    return {"headline": headline, "eta": eta, "reason": reason, "needs": action.missing_info or [], "note": action.info_request_note}


def _sync_message(db: Session, action: AgentAction) -> None:
    if not action.message_id:
        return
    msg = db.get(Message, action.message_id)
    if msg is None:
        return
    view = employee_view(action)
    msg.content = view["headline"] + (f" {action.result.get('outcome')}." if action.status == "EXECUTED" and action.result else "")
    msg.status = "pending_review" if action.status in OPEN_STATUSES else ("blocked" if action.status in ("BLOCKED", "REJECTED", "FAILED") else "delivered")
    msg.trust_status = {"EXECUTED": "verified", "BLOCKED": "blocked", "REJECTED": "blocked", "FAILED": "blocked"}.get(action.status, "needs_review")
    msg.updated_at = utcnow()


def _record_in_conversation(db: Session, action: AgentAction, user: User, conversation_id: int | None) -> None:
    conv = db.get(Conversation, conversation_id) if conversation_id else None
    if conv is None or conv.user_id != user.id:
        conv = Conversation(user_id=user.id, title=f"Action: {action.summary[:60]}")
        db.add(conv)
        db.flush()
    conv.updated_at = utcnow()
    db.add(Message(conversation_id=conv.id, role="user", content=action.request_text_masked or action.summary,
                   request_id=f"act-{action.id}", action_id=action.id))
    msg = Message(conversation_id=conv.id, role="assistant", content="", request_id=f"act-{action.id}", action_id=action.id,
                  explanation={"kind": "agent_action"})
    db.add(msg)
    db.flush()
    action.conversation_id, action.message_id = conv.id, msg.id
    _sync_message(db, action)


# --------------------------------------------------------------------------- lifecycle
def get_action(db: Session, action_id: int) -> AgentAction:
    a = db.get(AgentAction, action_id)
    if a is None:
        raise NotFound("Action")
    return a


def can_view(user: User, a: AgentAction) -> bool:
    return a.requested_by == user.id or user.has("agents:read") or (user.has("actions:approve") and a.required_approver_role in user.role_keys)


def request_action(db: Session, user: User, *, text: str | None = None, action_type: str | None = None, params: dict | None = None,
                   idempotency_key: str | None = None, conversation_id: int | None = None, record_in_conversation: bool = False) -> tuple[AgentAction, bool]:
    if not text and not action_type:
        raise BadRequest("Describe the action or give an action_type")
    if idempotency_key:
        existing = db.scalar(select(ActionIdempotencyKey).where(ActionIdempotencyKey.user_id == user.id, ActionIdempotencyKey.key == idempotency_key))
        if existing:
            return get_action(db, existing.action_id), False

    # 1. Input guardrails on the request text (injection, PII masking) — the same engine as chat.
    masked, injection, text_block = "", 0.0, None
    if text:
        engine = GuardrailEngine(policies.active_snapshots(db), get_pii_detector(), directory.directory_names(db))
        inp = engine.run_input(text, gateway.actor_from_user(user))
        masked = inp.sanitized_prompt
        injection = float(inp.stage.signals.get("injection_score", 0.0))
        if inp.stage.action in ("BLOCK", "ESCALATE") and any(m.risk_category == "prompt_injection" for m in inp.stage.matches):
            text_block = inp.stage.matches

    # 2. Classify.
    if action_type:
        at = db.scalar(select(ActionType).where(ActionType.key == action_type))
        if at is None:
            raise BadRequest(f"Unknown action type '{action_type}'")
        p = dict(params or {})
        c = Classified(action_type, p, p.pop("summary", None) or at.name, str(p.get("invoice_id") or p.get("claim_id") or p.get("subject") or ""),
                       p.get("amount"), bool(p.get("external", False)))
    else:
        c = classify(db, text or "")
    at = db.scalar(select(ActionType).where(ActionType.key == c.action_type)) if c.action_type else None

    action = AgentAction(requested_by=user.id, requester_email=user.email, requester_role=user.primary_role, action_type=c.action_type,
                         category=at.category if at else None, status="NEEDS_INFO", summary=c.summary[:500], target_system=at.target_system if at else "",
                         target_record=c.target_record[:200], params=c.params, amount=c.amount, currency="INR" if c.amount else None,
                         external=c.external, request_text_masked=masked, missing_info=c.missing)
    db.add(action)
    db.flush()
    _event(db, action, "requested", user, None, "REQUESTED", details={"text_masked": masked[:300]})
    roles = set(user.role_keys)
    agent = None
    if at is not None:
        agent = next((a for a in db.scalars(select(Agent).where(Agent.status == "active")) if at.key in (a.allowed_action_types or [])), None)
        action.agent_id = agent.id if agent else None

    # 3. Decide.
    if text_block:
        decision, approver, basis = "BLOCK", None, [{"policy_id": m.policy_id, "name": m.policy_name, "decision": "BLOCK", "reason": m.user_message} for m in text_block]
    elif at is None or c.missing:
        decision, approver, basis = "NEEDS_INFO", None, [{"policy_id": None, "name": "More information needed", "decision": "NEEDS_INFO",
                                                         "reason": "Please provide " + "; ".join(c.missing) + "."}]
    elif not at.is_enabled:
        decision, approver, basis = "BLOCK", None, [{"policy_id": None, "name": "Action disabled", "decision": "BLOCK", "reason": f"{at.name} is disabled."}]
    elif agent is None:
        decision, approver, basis = "BLOCK", None, [{"policy_id": None, "name": "No authorised agent", "decision": "BLOCK",
                                                    "reason": "No connected agent is allowed to perform this action."}]
    elif at.required_permission and not user.has(at.required_permission):
        decision, approver, basis = "BLOCK", None, [{"policy_id": None, "name": "Role permission", "decision": "BLOCK",
                                                    "reason": f"Your role does not include the {at.required_permission} permission required for this action."}]
    else:
        decision, approver, basis = evaluate_policies(db, at, c.amount, roles, c.external)
    action.risk_score = risk_score(at.category if at else "READ", c.amount, c.external, injection, text or c.summary)
    if decision not in ("BLOCK", "NEEDS_INFO") and action.risk_score >= ESCALATION_RISK:
        decision, approver = "ESCALATE", "security_admin"
        basis = [{"policy_id": None, "name": "Risk escalation", "decision": "ESCALATE",
                  "reason": f"Risk score {action.risk_score:.2f} is at or above the {ESCALATION_RISK:.2f} escalation threshold."}] + basis
    if decision == "ESCALATE" and not approver:
        approver = "security_admin"
    action.decision, action.required_approver_role, action.policy_basis = decision if decision != "NEEDS_INFO" else None, approver, basis

    status = {"EXECUTE": "APPROVED", "REQUIRE_APPROVAL": "PENDING_APPROVAL", "SEND_TO_REVIEW": "IN_REVIEW", "ESCALATE": "ESCALATED",
              "BLOCK": "BLOCKED", "NEEDS_INFO": "NEEDS_INFO"}[decision]
    action.status = "REQUESTED"
    if idempotency_key:
        db.add(ActionIdempotencyKey(user_id=user.id, key=idempotency_key, action_id=action.id))
    if record_in_conversation:
        _record_in_conversation(db, action, user, conversation_id)
    _set_status(db, action, status, user, "decided", f"Decision: {decision}", {"decision": decision, "approver_role": approver,
                                                                              "risk_score": action.risk_score, "basis": [b["name"] for b in basis]})
    if status in ("PENDING_APPROVAL", "IN_REVIEW", "ESCALATED"):
        db.add(ActionApproval(action_id=action.id, approver_role=approver or "security_admin"))
    try:
        db.commit()
    except IntegrityError:  # concurrent duplicate idempotency key
        db.rollback()
        existing = db.scalar(select(ActionIdempotencyKey).where(ActionIdempotencyKey.user_id == user.id, ActionIdempotencyKey.key == idempotency_key))
        return get_action(db, existing.action_id), False
    if decision == "EXECUTE":
        execute(db, action, user, auto=True)
    return get_action(db, action.id), True


def _open_approval(db: Session, action: AgentAction) -> ActionApproval | None:
    return db.scalar(select(ActionApproval).where(ActionApproval.action_id == action.id, ActionApproval.status == "PENDING")
                     .order_by(ActionApproval.id.desc()))


def _authorise_approver(action: AgentAction, user: User) -> None:
    if action.status not in ("PENDING_APPROVAL", "IN_REVIEW", "ESCALATED"):
        raise Conflict(f"This action is {action.status.replace('_', ' ').lower()} and is not awaiting approval")
    if user.id == action.requested_by:
        raise Forbidden("Separation of duties: you cannot approve an action you requested")
    if not user.has("actions:approve") or action.required_approver_role not in user.role_keys:
        raise Forbidden(f"This action must be approved by {ROLE_NAMES.get(action.required_approver_role or '', action.required_approver_role)}")


def _close_approval(db: Session, action: AgentAction, user: User, status: str, note: str) -> None:
    ap = _open_approval(db, action)
    if ap:
        ap.status, ap.decided_by, ap.decided_by_email, ap.note, ap.decided_at = status, user.id, user.email, note, utcnow()
    action.decided_at = utcnow()


def approve(db: Session, action: AgentAction, user: User, note: str = "") -> AgentAction:
    _authorise_approver(action, user)
    _close_approval(db, action, user, "APPROVED", note)
    _set_status(db, action, "APPROVED", user, "approved", note)
    db.commit()
    return execute(db, action, user, auto=True)


def reject(db: Session, action: AgentAction, user: User, note: str) -> AgentAction:
    if not note.strip():
        raise BadRequest("Tell the requester why the action was rejected")
    _authorise_approver(action, user)
    _close_approval(db, action, user, "REJECTED", note)
    _set_status(db, action, "REJECTED", user, "rejected", note)
    db.commit()
    return action


def request_info(db: Session, action: AgentAction, user: User, note: str) -> AgentAction:
    if not note.strip():
        raise BadRequest("Say what information is needed")
    _authorise_approver(action, user)
    _close_approval(db, action, user, "INFO_REQUESTED", note)
    action.info_request_note = note
    _set_status(db, action, "NEEDS_INFO", user, "info_requested", note)
    db.commit()
    return action


def escalate(db: Session, action: AgentAction, user: User, note: str = "") -> AgentAction:
    _authorise_approver(action, user)
    if action.status == "ESCALATED":
        raise Conflict("Already escalated")
    _close_approval(db, action, user, "ESCALATED", note)
    action.required_approver_role = "security_admin"
    db.add(ActionApproval(action_id=action.id, approver_role="security_admin"))
    _set_status(db, action, "ESCALATED", user, "escalated", note)
    db.commit()
    return action


def execute(db: Session, action: AgentAction, user: User, auto: bool = False) -> AgentAction:
    """Run the controlled executor. Requires an APPROVED action (or a FAILED one being retried)."""
    if action.status == "EXECUTED" or db.scalar(select(ActionExecution).where(ActionExecution.action_id == action.id,
                                                                               ActionExecution.status == "SUCCEEDED")):
        raise Conflict("This action has already been executed")
    if action.status not in ("APPROVED", "FAILED"):
        raise Conflict(f"This action is {action.status.replace('_', ' ').lower()}; it cannot run until it is approved")
    at = db.scalar(select(ActionType).where(ActionType.key == action.action_type))
    requester = db.get(User, action.requested_by)
    # Re-check permissions at execution time: a role change after approval must still stop the action.
    if at is None or requester is None or not requester.is_active or (at.required_permission and not requester.has(at.required_permission)):
        _set_status(db, action, "BLOCKED", user, "blocked_at_execution", "Requester no longer holds the required permission")
        db.commit()
        return action
    attempt = len(list(db.scalars(select(ActionExecution).where(ActionExecution.action_id == action.id)))) + 1
    _set_status(db, action, "EXECUTING", user, "executing", "Automatic" if auto else "Manual execution", {"attempt": attempt})
    db.commit()
    executor = get_executor(at.executor)
    ctx = ActionContext(action.id, requester.email, set(requester.permissions), user.email)
    run = ActionExecution(action_id=action.id, executor=at.executor, attempt=attempt, status="FAILED", executed_by_email=user.email)
    try:
        result = executor.execute(executor.validate(action.params or {}), ctx)
        run.status, run.result = "SUCCEEDED", result
    except ExecutorError as exc:
        run.error = str(exc)
    except Exception as exc:  # unexpected downstream failure: record safely, change nothing
        run.error = f"{type(exc).__name__}: {str(exc)[:300]}"
    run.finished_at = utcnow()
    db.add(run)
    try:
        db.flush()
    except IntegrityError:  # a concurrent run already succeeded — the unique index wins
        db.rollback()
        raise Conflict("This action has already been executed") from None
    if run.status == "SUCCEEDED":
        action.result, action.executed_at, action.error = run.result, utcnow(), None
        _set_status(db, action, "EXECUTED", user, "executed", run.result.get("outcome", ""), {"reference": run.result.get("reference"), "attempt": attempt})
    else:
        action.error = run.error
        _set_status(db, action, "FAILED", user, "execution_failed", run.error or "", {"attempt": attempt})
    db.commit()
    return action


def compensate(db: Session, action: AgentAction, user: User, note: str = "") -> AgentAction:
    if action.status != "EXECUTED":
        raise Conflict("Only executed actions can be compensated")
    at = db.scalar(select(ActionType).where(ActionType.key == action.action_type))
    run = db.scalar(select(ActionExecution).where(ActionExecution.action_id == action.id, ActionExecution.status == "SUCCEEDED"))
    executor = get_executor(at.executor)
    try:
        outcome = executor.compensate(run.result or {}, ActionContext(action.id, action.requester_email, set(), user.email))
    except ExecutorError as exc:
        raise Conflict(str(exc)) from None
    db.add(ActionExecution(action_id=action.id, executor=at.executor, attempt=run.attempt + 1, status="COMPENSATED", result=outcome,
                           executed_by_email=user.email, finished_at=utcnow()))
    action.result = {**(action.result or {}), "compensation": outcome}
    _set_status(db, action, "COMPENSATED", user, "compensated", note or outcome.get("outcome", ""), {"reference": outcome.get("reference")})
    db.commit()
    return action


# --------------------------------------------------------------------------- serialisation
def action_out(db: Session, a: AgentAction, detail: bool = False) -> dict[str, Any]:
    agent = db.get(Agent, a.agent_id) if a.agent_id else None
    out = {
        "id": a.id, "agent": {"key": agent.key, "name": agent.name} if agent else None, "requester_email": a.requester_email,
        "requester_role": a.requester_role, "action_type": a.action_type, "category": a.category, "status": a.status, "decision": a.decision,
        "summary": a.summary, "target_system": a.target_system, "target_record": a.target_record, "amount": a.amount, "currency": a.currency,
        "external": a.external, "risk_score": a.risk_score, "required_approver_role": a.required_approver_role, "policy_basis": a.policy_basis,
        "missing_info": a.missing_info, "info_request_note": a.info_request_note, "result": a.result, "error": a.error,
        "conversation_id": a.conversation_id, "created_at": _iso(a.created_at), "updated_at": _iso(a.updated_at),
        "decided_at": _iso(a.decided_at), "executed_at": _iso(a.executed_at), "employee_view": employee_view(a),
        "audit_reference": f"agent_action:{a.id}",
    }
    if detail:
        out["request_text_masked"] = a.request_text_masked
        out["params"] = a.params
        out["approvals"] = [{"id": x.id, "approver_role": x.approver_role, "status": x.status, "decided_by_email": x.decided_by_email,
                             "note": x.note, "created_at": _iso(x.created_at), "decided_at": _iso(x.decided_at)}
                            for x in db.scalars(select(ActionApproval).where(ActionApproval.action_id == a.id).order_by(ActionApproval.id))]
        out["executions"] = [{"id": x.id, "executor": x.executor, "attempt": x.attempt, "status": x.status, "result": x.result, "error": x.error,
                              "executed_by_email": x.executed_by_email, "started_at": _iso(x.started_at), "finished_at": _iso(x.finished_at)}
                             for x in db.scalars(select(ActionExecution).where(ActionExecution.action_id == a.id).order_by(ActionExecution.id))]
    return out


def audit_trail(db: Session, action_id: int) -> list[dict[str, Any]]:
    return [{"id": e.id, "event_type": e.event_type, "from_status": e.from_status, "to_status": e.to_status, "actor_email": e.actor_email,
             "actor_role": e.actor_role, "note": e.note, "details": e.details, "audit_event_id": e.audit_event_id, "created_at": _iso(e.created_at)}
            for e in db.scalars(select(ActionAuditEvent).where(ActionAuditEvent.action_id == action_id).order_by(ActionAuditEvent.id))]


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() + "Z" if d else None
