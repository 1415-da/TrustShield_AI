"""Connected-workspace / Slack adapter core.

Both inbound paths — the built-in workspace UI and real Slack (via Bolt) — call `handle_message`, which runs the
exact same `gateway.process` pipeline as the web assistant, with the channel's policy profile attached to the actor.

Guarantees
----------
* Idempotent: `event_id` is unique. A redelivery (Slack retry) increments `deliveries` and returns the original result;
  the gateway runs once.
* Rate-limited per user (sliding 60 s window).
* Only masked text is stored; replies are built from the gateway's masked output.
* When a reviewer resolves a held answer, `on_message_updated` pushes the final response back to the thread.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import sha256_hex
from app.models import ConnectedApp, Message, SlackEvent, SlackIdentity, User, WorkspaceChannel
from app.models.base import utcnow
from app.services import audit, gateway

log = logging.getLogger("trustshield.workspace")

RATE_LIMITED_TEXT = "You're sending messages faster than TrustShield allows. Please wait a moment and try again."
CHANNEL_OFF_TEXT = "This channel isn't connected to TrustShield yet. Ask a TrustShield admin to enable it."
UNLINKED_TEXT = "Your Slack account isn't linked to a NovaCorp identity, so TrustShield can't answer here yet."
REQUIRED_BOT_SCOPES = ["app_mentions:read", "channels:history", "chat:write", "users:read", "users:read.email"]


# --------------------------------------------------------------------------- outbound notifier
class Notifier(Protocol):
    def post(self, channel: str, text: str, blocks: list[dict] | None = None, thread_ts: str | None = None) -> None: ...


class SlackWebNotifier:
    """Posts to Slack with the Web API. Tokens are never logged."""

    def __init__(self, token: str) -> None:
        from slack_sdk import WebClient

        self.client = WebClient(token=token)

    def post(self, channel: str, text: str, blocks: list[dict] | None = None, thread_ts: str | None = None) -> None:
        self.client.chat_postMessage(channel=channel, text=text, blocks=blocks, thread_ts=thread_ts)


_notifier_override: Notifier | None = None


def set_notifier(notifier: Notifier | None) -> None:
    """Test hook: capture outbound Slack messages."""
    global _notifier_override
    _notifier_override = notifier


def notifier() -> Notifier | None:
    if _notifier_override is not None:
        return _notifier_override
    ok, _ = slack_configured()
    return SlackWebNotifier(get_settings().slack_bot_token) if ok else None


# --------------------------------------------------------------------------- config & rate limit
def slack_configured() -> tuple[bool, list[str]]:
    s = get_settings()
    missing = [name for name, value in (("SLACK_BOT_TOKEN", s.slack_bot_token), ("SLACK_SIGNING_SECRET", s.slack_signing_secret)) if not value]
    if not s.slack_enabled:
        missing = ["SLACK_ENABLED=true", *missing]
    return (not missing), missing


class RateLimiter:
    def __init__(self) -> None:
        self.hits: dict[int, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, user_id: int, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[user_id]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


limiter = RateLimiter()


# --------------------------------------------------------------------------- core
@dataclass
class Inbound:
    event_id: str
    source: str  # workspace | slack
    channel: WorkspaceChannel
    user: User | None
    text: str
    external_user_id: str | None = None
    thread_ts: str | None = None


def _app(db: Session, source: str) -> ConnectedApp | None:
    slug = "slack-integration" if source == "slack" else "connected-workspace"
    return db.scalar(select(ConnectedApp).where(ConnectedApp.slug == slug))


def _conversation_for(db: Session, user_id: int, channel_id: int) -> int | None:
    return db.scalar(select(SlackEvent.conversation_id).where(SlackEvent.user_id == user_id, SlackEvent.channel_id == channel_id,
                                                              SlackEvent.conversation_id.is_not(None)).order_by(SlackEvent.id.desc()).limit(1))


def handle_message(db: Session, inbound: Inbound) -> tuple[SlackEvent, bool]:
    """Process one inbound message. Returns (event, created). `created` is False for a redelivery."""
    existing = db.scalar(select(SlackEvent).where(SlackEvent.event_id == inbound.event_id))
    if existing is not None:
        existing.deliveries += 1
        audit.record(db, f"{existing.source}.event_redelivered", actor_user_id=existing.user_id,
                     details={"event_id": inbound.event_id, "deliveries": existing.deliveries, "status": existing.status})
        db.commit()
        return existing, False

    ev = SlackEvent(event_id=inbound.event_id, source=inbound.source, channel_id=inbound.channel.id,
                    user_id=inbound.user.id if inbound.user else None, external_user_id=inbound.external_user_id,
                    thread_ts=inbound.thread_ts, text_hash=sha256_hex(inbound.text), attempts=1)
    db.add(ev)
    db.flush()

    if inbound.user is None:
        ev.status, ev.error, ev.processed_at = "REJECTED_UNLINKED", "unlinked Slack user", utcnow()
    elif not inbound.channel.is_enabled:
        ev.status, ev.error, ev.processed_at = "REJECTED", "channel not enabled", utcnow()
    elif not inbound.user.has("assistant:use"):
        ev.status, ev.error, ev.processed_at = "REJECTED", "user lacks assistant:use", utcnow()
    elif not limiter.allow(inbound.user.id, get_settings().workspace_rate_limit_per_minute):
        ev.status, ev.error, ev.processed_at = "RATE_LIMITED", "per-user rate limit", utcnow()
    else:
        _process(db, ev, inbound)
        return ev, True
    ev.text_masked = gateway.mask_text(inbound.text)
    audit.record(db, f"{inbound.source}.event_rejected", actor_user_id=ev.user_id, app_id=_app_id(db, inbound.source),
                 details={"event_id": ev.event_id, "status": ev.status, "channel": inbound.channel.name})
    db.commit()
    return ev, True


def _app_id(db: Session, source: str) -> int | None:
    a = _app(db, source)
    return a.id if a else None


def _process(db: Session, ev: SlackEvent, inbound: Inbound) -> None:
    user = inbound.user
    assert user is not None
    db.commit()  # persist the RECEIVED row before the gateway runs (so failures are visible and retryable)
    try:
        r = gateway.process(db, actor=gateway.actor_from_user(user, profile=inbound.channel.profile_key), prompt=inbound.text,
                            app=_app(db, inbound.source), conversation_id=_conversation_for(db, user.id, inbound.channel.id),
                            source=inbound.source, title=f"#{inbound.channel.name}")
    except Exception as exc:
        db.rollback()
        ev = db.get(SlackEvent, ev.id)
        ev.status, ev.error = "FAILED", f"{type(exc).__name__}: {str(exc)[:300]}"
        ev.text_masked = gateway.mask_text(inbound.text)
        audit.record(db, f"{inbound.source}.event_failed", actor_user_id=user.id, details={"event_id": ev.event_id, "error": ev.error})
        db.commit()
        log.warning("workspace message failed", extra={"request_id": ev.event_id})
        return
    ev = db.get(SlackEvent, ev.id)
    ev.status, ev.processed_at = "PROCESSED", utcnow()
    ev.request_id, ev.conversation_id, ev.assistant_message_id = r.request_id, r.conversation_id, r.assistant_message_id
    ev.review_case_id, ev.trust_status, ev.input_action = r.review_case_id, r.trust_status, r.input_action.value
    ev.text_masked = r.sanitized_prompt
    db.commit()


def retry_event(db: Session, ev: SlackEvent, actor: User) -> SlackEvent:
    """Reprocess a FAILED event from its stored masked text (raw text is never retained)."""
    if ev.status != "FAILED":
        raise Conflict(f"Only failed events can be retried (this one is {ev.status.lower()})")
    user = db.get(User, ev.user_id) if ev.user_id else None
    channel = db.get(WorkspaceChannel, ev.channel_id) if ev.channel_id else None
    if user is None or channel is None:
        raise BadRequest("The original user or channel no longer exists")
    ev.attempts += 1
    audit.record(db, f"{ev.source}.event_retried", **audit.actor_fields(actor), details={"event_id": ev.event_id, "attempt": ev.attempts})
    _process(db, ev, Inbound(ev.event_id, ev.source, channel, user, ev.text_masked, ev.external_user_id, ev.thread_ts))
    return db.get(SlackEvent, ev.id)


# --------------------------------------------------------------------------- replies
def reply_for(db: Session, ev: SlackEvent) -> dict[str, Any]:
    """Structured reply for an event (used by the workspace UI and to build Slack blocks)."""
    if ev.status == "RATE_LIMITED":
        return {"kind": "notice", "text": RATE_LIMITED_TEXT, "trust_status": None}
    if ev.status == "REJECTED_UNLINKED":
        return {"kind": "notice", "text": UNLINKED_TEXT, "trust_status": None}
    if ev.status == "REJECTED":
        return {"kind": "notice", "text": CHANNEL_OFF_TEXT, "trust_status": None}
    if ev.status in ("RECEIVED", "FAILED"):
        return {"kind": "notice", "text": "TrustShield couldn't answer this message. An admin can retry it.", "trust_status": None}
    msg = db.get(Message, ev.assistant_message_id) if ev.assistant_message_id else None
    if msg is None:
        return {"kind": "notice", "text": "Response unavailable.", "trust_status": None}
    return {"kind": "answer", "text": msg.content, "trust_status": msg.trust_status, "status": msg.status, "citations": msg.citations or [],
            "explanation": msg.explanation, "message_id": msg.id, "conversation_id": ev.conversation_id, "request_id": ev.request_id,
            "review_case_id": ev.review_case_id, "updated_at": msg.updated_at.isoformat() + "Z"}


TRUST_LABEL = {"verified": "Verified", "redacted": "Redacted", "needs_review": "Under compliance review", "blocked": "Blocked by policy"}


def slack_blocks(ev: SlackEvent, reply: dict[str, Any]) -> tuple[str, list[dict]]:
    """Original, minimal Block Kit layout: answer, trust line, sources, deep link."""
    text = reply["text"]
    if reply.get("status") == "pending_review":
        text = "Your request is being reviewed by the compliance team. You'll get the answer here when it's ready."
    blocks: list[dict] = [{"type": "section", "text": {"type": "mrkdwn", "text": text[:2900]}}]
    context = []
    if reply.get("trust_status"):
        context.append(f"*TrustShield:* {TRUST_LABEL.get(reply['trust_status'], reply['trust_status'])}")
    expl = reply.get("explanation") or {}
    if reply.get("trust_status") in ("blocked", "needs_review", "redacted") and expl.get("headline"):
        context.append(expl["headline"])
    if reply.get("citations"):
        context.append("Sources: " + "; ".join(f"[{c['index']}] {c['title']}" for c in reply["citations"][:3]))
    if context:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": " · ".join(context)[:2900]}]})
    if reply.get("conversation_id"):
        url = f"{get_settings().public_app_url.rstrip('/')}/assistant?c={reply['conversation_id']}"
        blocks.append({"type": "actions", "elements": [{"type": "button", "action_id": "view_in_trustshield",
                                                        "text": {"type": "plain_text", "text": "View in TrustShield"}, "url": url}]})
    return text, blocks


def deliver_to_slack(db: Session, ev: SlackEvent, update: bool = False) -> bool:
    if ev.source != "slack":
        return False
    n = notifier()
    channel = db.get(WorkspaceChannel, ev.channel_id) if ev.channel_id else None
    if n is None or channel is None:
        return False
    text, blocks = slack_blocks(ev, reply_for(db, ev))
    try:
        n.post(channel.external_id, ("Update: " if update else "") + text, blocks, thread_ts=ev.thread_ts)
        return True
    except Exception as exc:  # pragma: no cover - network
        log.warning("slack delivery failed: %s", type(exc).__name__)
        return False


def on_message_updated(db: Session, message_id: int) -> None:
    """Called after a reviewer resolves a held answer: push the final response back to the originating thread."""
    ev = db.scalar(select(SlackEvent).where(SlackEvent.assistant_message_id == message_id))
    if ev is None:
        return
    msg = db.get(Message, message_id)
    ev.trust_status = msg.trust_status if msg else ev.trust_status
    ev.response_updated_at = utcnow()
    delivered = deliver_to_slack(db, ev, update=True)
    audit.record(db, f"{ev.source}.response_updated", actor_user_id=ev.user_id, request_id=ev.request_id,
                 review_case_id=ev.review_case_id, details={"event_id": ev.event_id, "trust_status": ev.trust_status,
                                                            "delivered_to_slack": delivered})
    db.commit()


# --------------------------------------------------------------------------- feed & admin views
def feed(db: Session, channel: WorkspaceChannel, viewer: User, limit: int = 60) -> list[dict[str, Any]]:
    """Channel history. Others' refused or held messages are withheld; private replies go only to the requester."""
    rows = list(db.scalars(select(SlackEvent).where(SlackEvent.channel_id == channel.id).order_by(SlackEvent.id.desc()).limit(limit)))
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows if r.user_id} or {-1})))}
    out = []
    for ev in reversed(rows):
        mine = ev.user_id == viewer.id
        reply = reply_for(db, ev)
        private = reply.get("trust_status") in ("blocked", "needs_review") or reply["kind"] == "notice"
        author = users.get(ev.user_id or -1)
        out.append({
            "event_id": ev.event_id, "id": ev.id, "source": ev.source, "created_at": ev.created_at.isoformat() + "Z", "is_mine": mine,
            "author": {"name": author.full_name if author else "Slack user", "department": author.department if author else ""},
            "text": ev.text_masked if (mine or not private) else None,
            "withheld": not mine and private,
            "reply": reply if (mine or not private) else {"kind": "private", "text": "TrustShield replied privately to the requester.", "trust_status": None},
        })
    return out


def event_out(db: Session, ev: SlackEvent) -> dict[str, Any]:
    channel = db.get(WorkspaceChannel, ev.channel_id) if ev.channel_id else None
    user = db.get(User, ev.user_id) if ev.user_id else None
    return {"id": ev.id, "event_id": ev.event_id, "source": ev.source, "channel": channel.name if channel else None,
            "user_email": user.email if user else None, "status": ev.status, "deliveries": ev.deliveries, "attempts": ev.attempts,
            "trust_status": ev.trust_status, "input_action": ev.input_action, "request_id": ev.request_id,
            "review_case_id": ev.review_case_id, "text_masked": ev.text_masked, "error": ev.error,
            "created_at": ev.created_at.isoformat() + "Z", "processed_at": ev.processed_at.isoformat() + "Z" if ev.processed_at else None,
            "response_updated_at": ev.response_updated_at.isoformat() + "Z" if ev.response_updated_at else None}


def status(db: Session) -> dict[str, Any]:
    s = get_settings()
    ok, missing = slack_configured()
    since = utcnow().replace(microsecond=0)
    counts = dict(db.execute(select(SlackEvent.status, func.count()).group_by(SlackEvent.status)).all())
    by_source = dict(db.execute(select(SlackEvent.source, func.count()).group_by(SlackEvent.source)).all())
    last = db.scalar(select(func.max(SlackEvent.created_at)))
    channels = list(db.scalars(select(WorkspaceChannel)))
    return {
        "slack": {"mode": "connected" if ok else ("disabled" if not s.slack_enabled else "not_configured"), "configured": ok,
                  "enabled": s.slack_enabled, "missing": missing, "workspace_name": s.slack_workspace_name or None,
                  "events_endpoint": "/api/integrations/slack/events", "interactions_endpoint": "/api/integrations/slack/interactions",
                  "required_bot_scopes": REQUIRED_BOT_SCOPES, "socket_mode_token_configured": bool(s.slack_app_token)},
        "workspace": {"enabled": True, "channels": len(channels), "enabled_channels": sum(1 for c in channels if c.is_enabled)},
        "events": {"by_status": counts, "by_source": by_source, "last_event_at": last.isoformat() + "Z" if last else None},
        "checked_at": since.isoformat() + "Z",
    }


def get_channel(db: Session, channel_id: int) -> WorkspaceChannel:
    c = db.get(WorkspaceChannel, channel_id)
    if c is None:
        raise NotFound("Channel")
    return c


def resolve_slack_user(db: Session, slack_user_id: str) -> User | None:
    """Map a Slack user to a TrustShield user: existing link, else Slack profile email (users:read.email)."""
    link = db.scalar(select(SlackIdentity).where(SlackIdentity.slack_user_id == slack_user_id))
    if link:
        return db.get(User, link.user_id)
    ok, _ = slack_configured()
    if not ok:
        return None
    try:  # pragma: no cover - network
        from slack_sdk import WebClient

        profile = WebClient(token=get_settings().slack_bot_token).users_info(user=slack_user_id)["user"]["profile"]
        email = (profile.get("email") or "").lower()
    except Exception:
        return None
    user = db.scalar(select(User).where(func.lower(User.email) == email)) if email else None
    if user:
        db.add(SlackIdentity(slack_user_id=slack_user_id, user_id=user.id, email=user.email))
        audit.record(db, "slack.identity_linked", actor_user_id=user.id, details={"slack_user_id": slack_user_id})
        db.commit()
    return user


def channel_for_slack(db: Session, external_id: str, name: str | None = None) -> WorkspaceChannel:
    """Known channel, or register an unknown Slack channel as *disabled* until an admin maps it."""
    c = db.scalar(select(WorkspaceChannel).where(WorkspaceChannel.external_id == external_id))
    if c is None:
        c = WorkspaceChannel(external_id=external_id, name=name or f"slack-{external_id.lower()}", source="slack", is_enabled=False,
                             profile_key="general", description="Discovered from Slack. Enable it to let TrustShield answer here.")
        db.add(c)
        audit.record(db, "slack.channel_discovered", details={"external_id": external_id})
        db.commit()
    return c
