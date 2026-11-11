"""Policy versioning & approval workflow.

Policies become families; behaviour lives in immutable version snapshots. Existing policies and their rules are
migrated into versions (the current state becomes the ACTIVE/INACTIVE version, older versions are ARCHIVED).
Role permissions for the new capabilities are merged additively.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11 11:42:03.733925
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table('policy_audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('policy_id', sa.Integer(), nullable=False),
    sa.Column('version_id', sa.Integer(), nullable=True),
    sa.Column('version_number', sa.Integer(), nullable=True),
    sa.Column('event_type', sa.String(length=40), nullable=False),
    sa.Column('from_status', sa.String(length=30), nullable=True),
    sa.Column('to_status', sa.String(length=30), nullable=True),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('actor_email', sa.String(length=255), nullable=True),
    sa.Column('actor_role', sa.String(length=64), nullable=True),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('audit_event_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_policy_audit_events_created_at'), 'policy_audit_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_policy_audit_events_event_type'), 'policy_audit_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_policy_audit_events_policy_id'), 'policy_audit_events', ['policy_id'], unique=False)
    op.create_table('policy_exceptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('policy_id', sa.Integer(), nullable=False),
    sa.Column('subject_type', sa.String(length=20), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('justification', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('requested_by', sa.Integer(), nullable=True),
    sa.Column('requested_by_email', sa.String(length=255), nullable=False),
    sa.Column('decided_by', sa.Integer(), nullable=True),
    sa.Column('decided_by_email', sa.String(length=255), nullable=True),
    sa.Column('decision_note', sa.Text(), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_policy_exceptions_created_at'), 'policy_exceptions', ['created_at'], unique=False)
    op.create_index(op.f('ix_policy_exceptions_policy_id'), 'policy_exceptions', ['policy_id'], unique=False)
    op.create_index(op.f('ix_policy_exceptions_status'), 'policy_exceptions', ['status'], unique=False)
    op.create_table('policy_approvals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('policy_id', sa.Integer(), nullable=False),
    sa.Column('version_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('requested_by', sa.Integer(), nullable=True),
    sa.Column('requested_by_email', sa.String(length=255), nullable=False),
    sa.Column('request_note', sa.Text(), nullable=False),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('decided_by', sa.Integer(), nullable=True),
    sa.Column('decided_by_email', sa.String(length=255), nullable=True),
    sa.Column('decision_note', sa.Text(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('impact', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['version_id'], ['policy_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_policy_approvals_policy_id'), 'policy_approvals', ['policy_id'], unique=False)
    op.create_index(op.f('ix_policy_approvals_status'), 'policy_approvals', ['status'], unique=False)
    op.create_index(op.f('ix_policy_approvals_version_id'), 'policy_approvals', ['version_id'], unique=False)
    op.create_table('policy_comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('policy_id', sa.Integer(), nullable=False),
    sa.Column('version_id', sa.Integer(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('author_email', sa.String(length=255), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['version_id'], ['policy_versions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_policy_comments_policy_id'), 'policy_comments', ['policy_id'], unique=False)

    # --- policy_versions: new lifecycle columns (nullable first, tightened after the data migration)
    for col in (
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('snapshot_hash', sa.String(length=64), nullable=True),
        sa.Column('based_on_version_id', sa.Integer(), nullable=True),
        sa.Column('effective_from', sa.DateTime(), nullable=True),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_by_email', sa.String(length=255), nullable=True),
        sa.Column('submitted_by', sa.Integer(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_by_email', sa.String(length=255), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('activated_by', sa.Integer(), nullable=True),
        sa.Column('activated_by_email', sa.String(length=255), nullable=True),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    ):
        op.add_column('policy_versions', col)
    op.add_column('policies', sa.Column('owner', sa.String(length=200), nullable=False, server_default=''))
    op.add_column('policies', sa.Column('review_cadence_days', sa.Integer(), nullable=False, server_default='180'))
    op.add_column('policies', sa.Column('active_version_id', sa.Integer(), nullable=True))
    op.add_column('policies', sa.Column('latest_version', sa.Integer(), nullable=False, server_default='0'))

    _migrate_data(bind)

    op.alter_column('policy_versions', 'status', nullable=False)
    op.alter_column('policy_versions', 'snapshot_hash', nullable=False)
    op.alter_column('policy_versions', 'created_by_email', nullable=False)
    op.alter_column('policy_versions', 'updated_at', nullable=False)
    op.create_index(op.f('ix_policy_versions_status'), 'policy_versions', ['status'], unique=False)
    op.create_index('uq_one_active_version', 'policy_versions', ['policy_id'], unique=True,
                    postgresql_where=sa.text("status = 'ACTIVE'"), sqlite_where=sa.text("status = 'ACTIVE'"))
    op.create_unique_constraint('uq_policy_version_number', 'policy_versions', ['policy_id', 'version'])
    op.drop_constraint('policy_versions_changed_by_fkey', 'policy_versions', type_='foreignkey')
    op.drop_column('policy_versions', 'changed_by')
    op.create_foreign_key('policy_versions_created_by_fkey', 'policy_versions', 'users', ['created_by'], ['id'])
    op.create_foreign_key('fk_policies_active_version', 'policies', 'policy_versions', ['active_version_id'], ['id'], ondelete='SET NULL')

    op.drop_index(op.f('ix_policy_rules_policy_id'), table_name='policy_rules')
    op.drop_table('policy_rules')
    op.drop_index(op.f('ix_policies_is_active'), table_name='policies')
    for col in ('is_active', 'user_message', 'sensitive_data_type', 'severity', 'action', 'description', 'version',
                'threshold', 'applicable_roles'):
        op.drop_column('policies', col)


RULE_COLS = ("name", "rule_type", "match_field", "pattern", "keywords", "entity_types", "topic", "required_permission",
             "threshold", "action", "severity", "applies_to_roles", "is_active")


def _json(v):  # JSONB comes back as python objects on psycopg; JSON text on other drivers
    return json.loads(v) if isinstance(v, str) else v


def _migrate_data(bind) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    emails = {r.id: r.email for r in bind.execute(sa.text("SELECT id, email FROM users"))}
    bind.execute(sa.text("UPDATE policy_versions SET status = 'ARCHIVED', created_by = changed_by, updated_at = created_at"))
    for uid, email in emails.items():
        bind.execute(sa.text("UPDATE policy_versions SET created_by_email = :e WHERE created_by = :u"), {"e": email, "u": uid})
    bind.execute(sa.text("UPDATE policy_versions SET created_by_email = 'system' WHERE created_by_email IS NULL"))

    policies = bind.execute(sa.text(
        "SELECT id, name, description, risk_category, sensitive_data_type, applicable_roles, action, severity, threshold, "
        "user_message, is_active, is_archived, created_by FROM policies")).mappings().all()
    for p in policies:
        rules = bind.execute(sa.text(
            f"SELECT id, {', '.join(RULE_COLS)} FROM policy_rules WHERE policy_id = :p ORDER BY id"), {"p": p["id"]}).mappings().all()
        definition = {
            "name": p["name"], "description": p["description"] or "", "risk_category": p["risk_category"],
            "sensitive_data_type": p["sensitive_data_type"], "owner": "", "review_cadence_days": 180,
            "applicable_roles": _json(p["applicable_roles"]) or [], "profiles": [], "action": p["action"],
            "severity": p["severity"], "threshold": p["threshold"], "user_message": p["user_message"] or "",
            "effective_from": None, "effective_to": None,
            "rules": [{"key": f"r{r['id']}", **{c: (_json(r[c]) if c in ("keywords", "entity_types", "applies_to_roles") else r[c])
                                               for c in RULE_COLS}} for r in rules],
        }
        digest = hashlib.sha256(json.dumps(definition, sort_keys=True, default=str).encode()).hexdigest()
        latest = bind.execute(sa.text("SELECT id, version FROM policy_versions WHERE policy_id = :p ORDER BY version DESC LIMIT 1"),
                              {"p": p["id"]}).first()
        status = "ARCHIVED" if p["is_archived"] else ("ACTIVE" if p["is_active"] else "INACTIVE")
        actor_email = emails.get(p["created_by"], "system")
        params = {"snap": json.dumps(definition), "h": digest, "s": status, "now": now, "by": p["created_by"], "email": actor_email}
        if latest is None:
            vid = bind.execute(sa.text(
                "INSERT INTO policy_versions (policy_id, version, snapshot, change_summary, created_at, status, snapshot_hash, "
                "created_by, created_by_email, updated_at) VALUES (:p, 1, CAST(:snap AS JSONB), 'Migrated', :now, :s, :h, :by, "
                ":email, :now) RETURNING id"), {**params, "p": p["id"]}).scalar()
            number = 1
        else:
            vid, number = latest.id, latest.version
            bind.execute(sa.text("UPDATE policy_versions SET snapshot = CAST(:snap AS JSONB), snapshot_hash = :h, status = :s, "
                                 "updated_at = :now WHERE id = :v"), {**params, "v": vid})
        # Pre-workflow versions were effectively approved by their author; record that honestly.
        bind.execute(sa.text("UPDATE policy_versions SET approved_by = :by, approved_by_email = :email || ' (pre-workflow)', "
                             "approved_at = :now, activated_by = CASE WHEN :s = 'ACTIVE' THEN :by END, "
                             "activated_by_email = CASE WHEN :s = 'ACTIVE' THEN :email END, "
                             "activated_at = CASE WHEN :s = 'ACTIVE' THEN CAST(:now AS TIMESTAMP) END WHERE id = :v"),
                     {**params, "v": vid})
        bind.execute(sa.text("UPDATE policy_versions SET snapshot_hash = '' WHERE snapshot_hash IS NULL AND policy_id = :p"), {"p": p["id"]})
        bind.execute(sa.text("UPDATE policies SET active_version_id = :a, latest_version = :n WHERE id = :p"),
                     {"a": vid if status == "ACTIVE" else None, "n": number, "p": p["id"]})
        bind.execute(sa.text(
            "INSERT INTO policy_audit_events (policy_id, version_id, version_number, event_type, from_status, to_status, note, "
            "details, created_at) VALUES (:p, :v, :n, 'migrated', NULL, :s, 'Migrated to versioned policy workflow', "
            "CAST('{}' AS JSONB), :now)"), {"p": p["id"], "v": vid, "n": number, "s": status, "now": now})
    bind.execute(sa.text("UPDATE policy_versions SET snapshot_hash = '' WHERE snapshot_hash IS NULL"))

    # Merge default permissions into existing roles and create new roles.
    from app.core.permissions import DEFAULT_ROLES

    for role in DEFAULT_ROLES:
        row = bind.execute(sa.text("SELECT id, permissions FROM roles WHERE key = :k"), {"k": role["key"]}).first()
        if row is None:
            bind.execute(sa.text("INSERT INTO roles (key, name, description, permissions, is_system, created_at) "
                                 "VALUES (:k, :n, :d, CAST(:p AS JSONB), true, :now)"),
                         {"k": role["key"], "n": role["name"], "d": role["description"], "p": json.dumps(role["permissions"]), "now": now})
        else:
            merged = sorted(set(_json(row.permissions) or []) | set(role["permissions"]))
            bind.execute(sa.text("UPDATE roles SET permissions = CAST(:p AS JSONB), description = :d WHERE id = :i"),
                         {"p": json.dumps(merged), "d": role["description"], "i": row.id})


def downgrade() -> None:
    raise NotImplementedError("0002 migrates policy data into immutable versions and cannot be reversed automatically; "
                              "restore from a backup taken before upgrading.")
