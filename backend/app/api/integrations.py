"""Slack integration (admin + Slack-facing endpoints) and the built-in connected workspace (employee-facing)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import BadRequest, NotFound
from app.models import PolicyProfile, SlackEvent, User, WorkspaceChannel
from app.models.base import utcnow
from app.services import audit, workspace
from app.services.slack_bolt_app import handler

router = APIRouter(tags=["integrations"])
can_read = require_permission("integrations:read")
can_manage = require_permission("integrations:manage")
can_use = require_permission("assistant:use")

NOT_CONFIGURED = {"ok": False, "status": "not_configured",
                  "message": "Slack connection not configured. The TrustShield connected workspace remains fully available."}


# --------------------------------------------------------------------------- Slack-facing (signed by Slack)
@router.post("/integrations/slack/events")
async def slack_events(request: Request):
    """Slack Events API endpoint. Signature verification, url_verification and dispatch are handled by Bolt."""
    h = handler()
    if h is None:
        return JSONResponse(NOT_CONFIGURED, status_code=200)  # 200 so Slack does not retry-storm a disabled endpoint
    return await h.handle(request)


@router.post("/integrations/slack/interactions")
async def slack_interactions(request: Request):
    h = handler()
    if h is None:
        return JSONResponse(NOT_CONFIGURED, status_code=200)
    return await h.handle(request)


# --------------------------------------------------------------------------- admin
class ChannelPatch(BaseModel):
    profile_key: str | None = None
    is_enabled: bool | None = None
    policy_hint: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=500)


def _channel(c: WorkspaceChannel, profiles: dict[str, PolicyProfile]) -> dict:
    p = profiles.get(c.profile_key)
    return {"id": c.id, "external_id": c.external_id, "name": c.name, "description": c.description, "policy_hint": c.policy_hint,
            "profile_key": c.profile_key, "profile_name": p.name if p else c.profile_key, "source": c.source, "is_enabled": c.is_enabled,
            "updated_at": c.updated_at.isoformat() + "Z"}


def _profiles(db: Session) -> dict[str, PolicyProfile]:
    return {p.key: p for p in db.scalars(select(PolicyProfile))}


@router.get("/integrations/slack/status")
def slack_status(_: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    return workspace.status(db)


@router.post("/integrations/slack/test")
def slack_test(user: User = Depends(can_manage), db: Session = Depends(get_db)) -> dict:
    ok, missing = workspace.slack_configured()
    result: dict = {"tested_at": utcnow().isoformat() + "Z", "workspace_ok": True,
                    "workspace_channels": len(list(db.scalars(select(WorkspaceChannel).where(WorkspaceChannel.is_enabled.is_(True)))))}
    if not ok:
        result.update({"ok": False, "mode": "not_configured", "missing": missing,
                       "message": "Slack connection not configured. The connected workspace is healthy."})
    else:  # pragma: no cover - network
        try:
            from slack_sdk import WebClient

            from app.core.config import get_settings

            auth = WebClient(token=get_settings().slack_bot_token).auth_test()
            result.update({"ok": True, "mode": "connected", "team": auth.get("team"), "bot_user": auth.get("user")})
        except Exception as exc:
            result.update({"ok": False, "mode": "error", "message": f"Slack rejected the credentials ({type(exc).__name__})."})
    audit.record(db, "slack.connection_tested", **audit.actor_fields(user), details={k: v for k, v in result.items() if k != "missing"}, commit=True)
    return result


@router.get("/integrations/slack/channels")
def list_channels(_: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    profiles = _profiles(db)
    return {"channels": [_channel(c, profiles) for c in db.scalars(select(WorkspaceChannel).order_by(WorkspaceChannel.name))],
            "profiles": [{"key": p.key, "name": p.name, "description": p.description} for p in profiles.values()]}


@router.patch("/integrations/slack/channels/{channel_id}")
def update_channel(channel_id: int, body: ChannelPatch, user: User = Depends(can_manage), db: Session = Depends(get_db)) -> dict:
    c = workspace.get_channel(db, channel_id)
    profiles = _profiles(db)
    changes = body.model_dump(exclude_none=True)
    if "profile_key" in changes and changes["profile_key"] not in profiles:
        raise BadRequest("Unknown policy profile")
    before = {k: getattr(c, k) for k in changes}
    for k, v in changes.items():
        setattr(c, k, v)
    audit.record(db, "slack.channel_updated", **audit.actor_fields(user), details={"channel": c.name, "before": before, "after": changes})
    db.commit()
    return _channel(c, profiles)


@router.get("/integrations/slack/events")
def list_events(status: str | None = None, source: str | None = None, limit: int = Query(100, ge=1, le=500),
                _: User = Depends(can_read), db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(SlackEvent).order_by(SlackEvent.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(SlackEvent.status == status.upper())
    if source:
        stmt = stmt.where(SlackEvent.source == source)
    return [workspace.event_out(db, e) for e in db.scalars(stmt)]


@router.post("/integrations/slack/retry/{event_id}")
def retry(event_id: str, user: User = Depends(can_manage), db: Session = Depends(get_db)) -> dict:
    ev = db.scalar(select(SlackEvent).where(SlackEvent.event_id == event_id))
    if ev is None:
        raise NotFound("Event")
    return workspace.event_out(db, workspace.retry_event(db, ev, user))


# --------------------------------------------------------------------------- connected workspace (employees)
class WorkspaceMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    client_msg_id: str | None = Field(default=None, max_length=64, description="Idempotency key from the client")


@router.get("/workspace/channels")
def workspace_channels(_: User = Depends(can_use), db: Session = Depends(get_db)) -> list[dict]:
    profiles = _profiles(db)
    return [_channel(c, profiles) for c in db.scalars(select(WorkspaceChannel).where(WorkspaceChannel.is_enabled.is_(True),
                                                                                       WorkspaceChannel.source == "internal")
                                                      .order_by(WorkspaceChannel.name))]


@router.get("/workspace/channels/{channel_id}/messages")
def channel_messages(channel_id: int, user: User = Depends(can_use), db: Session = Depends(get_db)) -> list[dict]:
    c = workspace.get_channel(db, channel_id)
    if not c.is_enabled:
        raise NotFound("Channel")
    return workspace.feed(db, c, user)


@router.post("/workspace/channels/{channel_id}/messages", status_code=201)
def post_message(channel_id: int, body: WorkspaceMessage, user: User = Depends(can_use), db: Session = Depends(get_db)) -> dict:
    c = workspace.get_channel(db, channel_id)
    key = f"ws:{user.id}:{body.client_msg_id}" if body.client_msg_id else f"ws:{uuid.uuid4().hex}"
    ev, _created = workspace.handle_message(db, workspace.Inbound(event_id=key, source="workspace", channel=c, user=user, text=body.text))
    return next(item for item in workspace.feed(db, c, user, limit=200) if item["event_id"] == ev.event_id)
