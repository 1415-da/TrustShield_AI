"""organization workspaces (tenant isolation)

Creates `organizations`, puts every existing row in workspace 1 (NovaCorp), adds `organization_id` to every
business table, and turns name/key uniqueness into per-organization uniqueness.

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "users", "employee_records", "connected_apps", "api_keys", "policies", "policy_versions", "policy_approvals",
    "policy_comments", "policy_audit_events", "policy_exceptions", "documents", "document_chunks", "conversations",
    "messages", "guardrail_decisions", "audit_events", "review_cases", "review_actions", "test_cases", "test_runs",
    "test_results", "compliance_reports", "report_schedules", "policy_profiles", "workspace_channels",
    "slack_identities", "slack_events", "agents", "action_types", "action_policies", "agent_actions",
    "action_approvals", "action_executions", "action_audit_events", "action_idempotency_keys",
]

# (table, column, existing global unique constraint or None, existing global unique index or None)
PER_ORG_UNIQUE = [
    ("policies", "name", "policies_name_key", None),
    ("connected_apps", "name", "connected_apps_name_key", None),
    ("connected_apps", "slug", None, "ix_connected_apps_slug"),
    ("test_cases", "code", "test_cases_code_key", None),
    ("policy_profiles", "key", None, "ix_policy_profiles_key"),
    ("workspace_channels", "name", "workspace_channels_name_key", None),
    ("workspace_channels", "external_id", None, "ix_workspace_channels_external_id"),
    ("agents", "key", None, "ix_agents_key"),
    ("action_types", "key", None, "ix_action_types_key"),
    ("action_policies", "name", "action_policies_name_key", None),
    ("employee_records", "employee_code", None, "ix_employee_records_employee_code"),
]


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("industry", sa.String(80), nullable=False, server_default=""),
        sa.Column("size", sa.String(40), nullable=False, server_default=""),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.execute("INSERT INTO organizations (id, name, slug, industry, size, is_demo) "
               "VALUES (1, 'NovaCorp', 'novacorp', 'Technology', '1,000–5,000', true)")
    op.execute("SELECT setval(pg_get_serial_sequence('organizations', 'id'), 1)")

    # ADD COLUMN with a default fills existing rows without firing row triggers (audit_events stays append-only).
    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=False, server_default="1"))
        op.alter_column(table, "organization_id", server_default=None)
        op.create_foreign_key(f"fk_{table}_organization", table, "organizations", ["organization_id"], ["id"], ondelete="CASCADE")
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])

    for table, column, constraint, index in PER_ORG_UNIQUE:
        if constraint:
            op.drop_constraint(constraint, table, type_="unique")
        if index:
            op.drop_index(index, table_name=table)
            op.create_index(index, table, [column])
        op.create_unique_constraint(f"uq_{table}_{column}_per_org", table, ["organization_id", column])


def downgrade() -> None:
    raise RuntimeError("0006 introduces organization workspaces and cannot be downgraded safely; restore from backup.")
