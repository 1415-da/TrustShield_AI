"""ORM models. Importing this package registers every table on `Base.metadata`."""

from app.models.agents import (ActionApproval, ActionAuditEvent, ActionExecution, ActionIdempotencyKey, ActionPolicy, ActionType, Agent,
                               AgentAction)
from app.models.apps import ApiKey, ConnectedApp
from app.models.compliance import ComplianceReport, ReportSchedule
from app.models.conversation import Conversation, Message
from app.models.document import Document, DocumentChunk
from app.models.governance import AuditEvent, GuardrailDecision, ReviewAction, ReviewCase
from app.models.organization import DEFAULT_ORG_ID, Organization, TenantMixin
from app.models.policy import Policy, PolicyApproval, PolicyAuditEvent, PolicyComment, PolicyException, PolicyVersion
from app.models.testing import TestCase, TestResult, TestRun
from app.models.user import AuthSession, EmployeeRecord, Role, User, user_roles
from app.models.workspace import PolicyProfile, SlackEvent, SlackIdentity, WorkspaceChannel

__all__ = [
    "DEFAULT_ORG_ID", "Organization", "TenantMixin",
    "ActionApproval", "ActionAuditEvent", "ActionExecution", "ActionIdempotencyKey", "ActionPolicy", "ActionType", "Agent", "AgentAction",
    "PolicyProfile", "SlackEvent", "SlackIdentity", "WorkspaceChannel",
    "ApiKey", "AuditEvent", "ComplianceReport", "ReportSchedule", "ConnectedApp", "Conversation", "Document", "DocumentChunk", "EmployeeRecord",
    "GuardrailDecision", "Message", "Policy", "PolicyApproval", "PolicyAuditEvent", "PolicyComment", "PolicyException", "PolicyVersion", "ReviewAction", "ReviewCase",
    "AuthSession", "Role", "TestCase", "TestResult", "TestRun", "User", "user_roles",
]

# Tenant scoping hooks are registered on import so every Session is isolated by organization.
import app.core.tenancy  # noqa: E402,F401
