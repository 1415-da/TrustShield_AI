"""consistent roles: canonical names, separation of duties, everyone is an employee

* Role names and descriptions follow `app.core.permissions.DEFAULT_ROLES` (e.g. "Security Auditor").
* TrustShield Admin no longer decides held answers (`reviews:act`); Compliance Reviewers do.
* The NovaCorp admin (rohan.das@novacorp.test) no longer also holds Compliance Reviewer.
* Every user holds the base `employee` role plus their job role.

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.permissions import DEFAULT_ROLES

    conn = op.get_bind()
    for r in DEFAULT_ROLES:
        conn.execute(sa.text("UPDATE roles SET name = :n, description = :d WHERE key = :k"),
                     {"n": r["name"], "d": r["description"], "k": r["key"]})

    row = conn.execute(sa.text("SELECT id, permissions FROM roles WHERE key = 'trustshield_admin'")).first()
    if row is not None:
        perms = row.permissions if isinstance(row.permissions, list) else json.loads(row.permissions or "[]")
        if "reviews:act" in perms:
            perms = sorted(p for p in perms if p != "reviews:act")
            conn.execute(sa.text("UPDATE roles SET permissions = CAST(:p AS JSONB) WHERE id = :id"),
                         {"p": json.dumps(perms), "id": row.id})

    conn.execute(sa.text("""
        DELETE FROM user_roles
        WHERE user_id IN (SELECT id FROM users WHERE lower(email) = 'rohan.das@novacorp.test')
          AND role_id IN (SELECT id FROM roles WHERE key = 'compliance_reviewer')
    """))

    conn.execute(sa.text("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id FROM users u CROSS JOIN roles r
        WHERE r.key = 'employee'
          AND NOT EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id AND ur.role_id = r.id)
    """))


def downgrade() -> None:
    # Data-only alignment; the previous state was inconsistent by design of this fix, so it is not restored.
    pass
