"""Controlled action executors.

An executor is the *only* way an agent action touches a system of record. TrustShield calls `execute` only after the
action has been authorised (and approved where required); the executor still validates its own input and the action
service re-checks the requester's permissions immediately before calling it.

These executors talk to in-process mock systems of record so the product can be demonstrated offline. Swapping in a
real integration means implementing the same interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

# --------------------------------------------------------------------------- mock systems of record (developer note: all records are synthetic)
EXPENSE_CLAIMS: dict[str, dict[str, Any]] = {
    "EXP-1042": {"employee": "Priya Nair", "amount": 3200.0, "description": "Client lunch, Mumbai"},
    "EXP-1057": {"employee": "Arjun Mehta", "amount": 18500.0, "description": "Conference travel, Bengaluru"},
    "EXP-1063": {"employee": "Meera Iyer", "amount": 72000.0, "description": "Team offsite venue deposit"},
    "EXP-1071": {"employee": "Ravi Sharma", "amount": 4100.0, "description": "Home office chair"},
}
VENDOR_INVOICES: dict[str, dict[str, Any]] = {
    "INV-2291": {"vendor": "Orion Supplies", "amount": 18000.0, "reason": "Duplicate invoice"},
    "INV-2304": {"vendor": "Kestrel Logistics", "amount": 6400.0, "reason": "Damaged shipment"},
    "INV-2318": {"vendor": "Banyan Analytics", "amount": 145000.0, "reason": "Cancelled annual subscription"},
}
LEAVE_BALANCES: dict[str, float] = {"Ravi Sharma": 14, "Priya Nair": 9, "Arjun Mehta": 21, "Meera Iyer": 11, "Sneha Joshi": 17}


@dataclass
class ActionContext:
    action_id: int
    requester_email: str
    requester_permissions: set[str]
    executed_by_email: str


class ExecutorError(RuntimeError):
    """Raised for validation or downstream failures. Nothing is changed when this is raised."""


class ActionExecutor(ABC):
    key: str = "base"
    input_model: type[BaseModel] = BaseModel

    def validate(self, params: dict[str, Any]) -> BaseModel:
        try:
            return self.input_model.model_validate(params)
        except ValidationError as exc:
            raise ExecutorError(f"Invalid input for {self.key}: {exc.errors()[0]['msg']}") from None

    @abstractmethod
    def execute(self, params: BaseModel, ctx: ActionContext) -> dict[str, Any]: ...

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        raise ExecutorError(f"{self.key} cannot be compensated automatically; raise a manual correction ticket")


class _ClaimIn(BaseModel):
    claim_id: str
    amount: float = Field(gt=0)


class ExpenseReimbursementExecutor(ActionExecutor):
    key, input_model = "expense_reimbursement", _ClaimIn

    def execute(self, params: _ClaimIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        claim = EXPENSE_CLAIMS.get(params.claim_id)
        if claim is None:
            raise ExecutorError(f"Expense claim {params.claim_id} not found")
        if abs(claim["amount"] - params.amount) > 0.01:
            raise ExecutorError("Amount does not match the submitted claim")
        return {"reference": f"RMB-{ctx.action_id:05d}", "claim_id": params.claim_id, "employee": claim["employee"],
                "amount": params.amount, "currency": "INR", "outcome": "Reimbursement approved and scheduled for the next payroll run"}

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        return {"reference": f"REV-{ctx.action_id:05d}", "outcome": f"Reimbursement {result.get('reference')} reversed before payout"}


class _RefundIn(BaseModel):
    invoice_id: str
    amount: float = Field(gt=0)


class VendorRefundExecutor(ActionExecutor):
    key, input_model = "vendor_refund", _RefundIn

    def execute(self, params: _RefundIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        inv = VENDOR_INVOICES.get(params.invoice_id)
        if inv is None:
            raise ExecutorError(f"Invoice {params.invoice_id} not found")
        if params.amount > inv["amount"] + 0.01:
            raise ExecutorError("Refund exceeds the invoice amount")
        return {"reference": f"RFD-{ctx.action_id:05d}", "invoice_id": params.invoice_id, "vendor": inv["vendor"], "amount": params.amount,
                "currency": "INR", "outcome": "Refund recorded in the Finance Operations portal"}

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        return {"reference": f"RFV-{ctx.action_id:05d}", "outcome": f"Refund {result.get('reference')} voided"}


class _LeaveIn(BaseModel):
    employee: str
    days: float = Field(ge=0, le=60)


class LeaveUpdateExecutor(ActionExecutor):
    key, input_model = "leave_update", _LeaveIn

    def execute(self, params: _LeaveIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        if params.employee not in LEAVE_BALANCES:
            raise ExecutorError(f"No leave record for {params.employee}")
        return {"reference": f"LV-{ctx.action_id:05d}", "employee": params.employee, "previous_days": LEAVE_BALANCES[params.employee],
                "new_days": params.days, "outcome": "Leave balance updated in the HR system"}

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        return {"reference": f"LVR-{ctx.action_id:05d}", "outcome": f"Leave balance restored to {result.get('previous_days')} days"}


class _TicketIn(BaseModel):
    summary: str = Field(min_length=3, max_length=300)
    priority: str = "Medium"


class TicketExecutor(ActionExecutor):
    key, input_model = "ticket", _TicketIn

    def execute(self, params: _TicketIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        return {"reference": f"SEC-{1200 + ctx.action_id}", "summary": params.summary, "priority": params.priority,
                "outcome": "Ticket created in the issue tracker"}

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        return {"reference": result.get("reference"), "outcome": "Ticket closed as created in error"}


class _NotifyIn(BaseModel):
    recipient: str = Field(min_length=2)
    message: str = Field(min_length=3, max_length=2000)
    external: bool = False


class NotificationExecutor(ActionExecutor):
    key, input_model = "notification", _NotifyIn

    def execute(self, params: _NotifyIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        return {"reference": f"MSG-{ctx.action_id:05d}", "recipient": params.recipient, "external": params.external,
                "outcome": "Message queued for delivery"}


class _LookupIn(BaseModel):
    subject: str = ""


class LeaveBalanceExecutor(ActionExecutor):
    key, input_model = "leave_balance", _LookupIn

    def execute(self, params: _LookupIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        return {"reference": f"LVQ-{ctx.action_id:05d}", "outcome": "You have 14 days of annual leave and 9 sick days remaining."}


class SalaryBandExecutor(ActionExecutor):
    key, input_model = "salary_band", _LookupIn

    def execute(self, params: _LookupIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        if "data:compensation" not in ctx.requester_permissions:
            raise ExecutorError("Compensation data scope required")
        return {"reference": f"HRQ-{ctx.action_id:05d}", "outcome": f"Salary band lookup for {params.subject or 'the employee'} is available in the HR system."}


class _ChangeIn(BaseModel):
    subject: str = Field(min_length=2)
    change: str = Field(min_length=3)


class SalaryUpdateExecutor(ActionExecutor):
    key, input_model = "salary_update", _ChangeIn

    def execute(self, params: _ChangeIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        return {"reference": f"CMP-{ctx.action_id:05d}", "outcome": f"Compensation change for {params.subject} recorded for the next payroll cycle"}

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        return {"reference": f"CMPR-{ctx.action_id:05d}", "outcome": "Compensation change withdrawn before payroll"}


class AccessRevokeExecutor(ActionExecutor):
    key, input_model = "access_revoke", _ChangeIn

    def execute(self, params: _ChangeIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        return {"reference": f"IAM-{ctx.action_id:05d}", "outcome": f"Access revoked for {params.subject}"}

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        return {"reference": f"IAMR-{ctx.action_id:05d}", "outcome": "Access restored"}


class RecordDeleteExecutor(ActionExecutor):
    key, input_model = "record_delete", _ChangeIn

    def execute(self, params: _ChangeIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        return {"reference": f"DEL-{ctx.action_id:05d}", "outcome": f"{params.subject} moved to the 30-day recovery bin"}

    def compensate(self, result: dict[str, Any], ctx: ActionContext) -> dict[str, Any]:
        return {"reference": f"DELR-{ctx.action_id:05d}", "outcome": "Record restored from the recovery bin"}


class AdminChangeExecutor(ActionExecutor):
    key, input_model = "admin_change", _ChangeIn

    def execute(self, params: _ChangeIn, ctx: ActionContext) -> dict[str, Any]:  # type: ignore[override]
        # Agents never edit governance configuration directly: an approved admin action opens a change request.
        return {"reference": f"CHG-{ctx.action_id:05d}", "outcome": f"Change request opened: {params.change}"}


EXECUTORS: dict[str, ActionExecutor] = {e.key: e for e in (
    ExpenseReimbursementExecutor(), VendorRefundExecutor(), LeaveUpdateExecutor(), TicketExecutor(), NotificationExecutor(),
    LeaveBalanceExecutor(), SalaryBandExecutor(), SalaryUpdateExecutor(), AccessRevokeExecutor(), RecordDeleteExecutor(),
    AdminChangeExecutor(),
)}


def get_executor(key: str) -> ActionExecutor:
    try:
        return EXECUTORS[key]
    except KeyError:
        raise ExecutorError(f"No executor registered for {key}") from None
