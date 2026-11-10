#!/usr/bin/env python3
"""Seed the synthetic NovaCorp demo tenant.

Usage (from the repository root or inside the backend container):

    python scripts/seed_demo_data.py              # seed (fails if data exists)
    python scripts/seed_demo_data.py --if-empty   # seed only when the database is empty (used by Docker)
    python scripts/seed_demo_data.py --reset      # drop all data, re-run migrations, seed again

All data is fictional. Demo accounts use DEMO_USER_PASSWORD (see .env.example).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend" if (ROOT / "backend").exists() else Path("/srv/backend")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.seed.loader import is_seeded, seed_all  # noqa: E402


def reset_database() -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, cwd=BACKEND)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--if-empty", action="store_true", help="skip if users already exist")
    parser.add_argument("--reset", action="store_true", help="drop and recreate the schema first")
    parser.add_argument("--no-history", action="store_true", help="skip back-filled traffic")
    args = parser.parse_args()

    if args.reset:
        reset_database()
    with SessionLocal() as db:
        if is_seeded(db):
            if args.if_empty:
                print("[seed] database already seeded — skipping")
                return 0
            print("[seed] database already contains data; use --reset to start over", file=sys.stderr)
            return 1
        summary = seed_all(db, get_settings().demo_user_password, history=not args.no_history)
    print("[seed] done:", json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
