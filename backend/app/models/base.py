"""Shared column helpers. Timestamps are stored as naive UTC and serialised with a `Z` suffix."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
