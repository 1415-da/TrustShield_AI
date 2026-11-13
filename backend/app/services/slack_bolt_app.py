"""Real Slack mode: a Slack Bolt app mounted on FastAPI through Bolt's ASGI (Starlette) adapter.

Bolt verifies request signatures (X-Slack-Signature / X-Slack-Request-Timestamp), answers url_verification, and
dispatches events to the listeners below, which call the same adapter core as the built-in workspace.
`process_before_response=True` keeps processing inside the request so nothing is lost if the process restarts;
the gateway answers well within Slack's 3-second budget for typical requests.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services import workspace

from app.core.tenancy import use_org  # noqa: E402
from app.models.organization import DEFAULT_ORG_ID  # noqa: E402

log = logging.getLogger("trustshield.slack")


def _on_message(body: dict, event: dict) -> None:
    if event.get("bot_id") or event.get("subtype"):  # ignore bot echoes, edits, joins
        return
    with SessionLocal() as db:
        # The Slack app is connected to the platform (NovaCorp) workspace; bind it explicitly.
        use_org(db, DEFAULT_ORG_ID)
        user = workspace.resolve_slack_user(db, event.get("user", ""))
        channel = workspace.channel_for_slack(db, event.get("channel", ""))
        text = (event.get("text") or "").split(">", 1)[-1].strip() if event.get("type") == "app_mention" else (event.get("text") or "")
        ev, created = workspace.handle_message(db, workspace.Inbound(
            event_id=body.get("event_id") or f"{event.get('channel')}:{event.get('ts')}", source="slack", channel=channel, user=user,
            text=text, external_user_id=event.get("user"), thread_ts=event.get("thread_ts") or event.get("ts")))
        if created:
            workspace.deliver_to_slack(db, ev)


@lru_cache(maxsize=4)
def _build(token: str, signing_secret: str):  # type: ignore[no-untyped-def]
    from slack_bolt import App
    from slack_bolt.adapter.fastapi import SlackRequestHandler
    from slack_bolt.authorization import AuthorizeResult

    def authorize(enterprise_id, team_id, **_):  # type: ignore[no-untyped-def]
        # Single-workspace install: authorise with the configured bot token without a per-request auth.test call.
        return AuthorizeResult(enterprise_id=enterprise_id, team_id=team_id, bot_token=token)

    bolt = App(signing_secret=signing_secret, authorize=authorize, process_before_response=True,
               raise_error_for_unhandled_request=False, ignoring_self_events_enabled=False)

    @bolt.event("message")
    def handle_message(body, event):  # type: ignore[no-untyped-def]
        _on_message(body, event)

    @bolt.event("app_mention")
    def handle_mention(body, event):  # type: ignore[no-untyped-def]
        _on_message(body, event)

    @bolt.action("view_in_trustshield")
    def view_link(ack):  # type: ignore[no-untyped-def]
        ack()  # URL button: Slack opens the link; we only acknowledge

    return SlackRequestHandler(bolt)


def handler():  # type: ignore[no-untyped-def]
    ok, _ = workspace.slack_configured()
    if not ok:
        return None
    s = get_settings()
    return _build(s.slack_bot_token, s.slack_signing_secret)
