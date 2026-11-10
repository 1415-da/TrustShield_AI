"""Employee assistant endpoints. All model access goes through the gateway service."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission, resolve_app
from app.core.errors import NotFound
from app.models import ConnectedApp, Conversation, Message, User
from app.schemas.assistant import ChatRequest, ChatResponse, ConversationDetail, ConversationSummary, MessageOut
from app.services import gateway

router = APIRouter(prefix="/assistant", tags=["assistant"])
use_assistant = require_permission("assistant:use")


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: User = Depends(use_assistant), app: ConnectedApp | None = Depends(resolve_app),
         db: Session = Depends(get_db)) -> dict:
    if body.conversation_id is not None:
        conv = db.get(Conversation, body.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise NotFound("Conversation")
    r = gateway.process(db, actor=gateway.actor_from_user(user), prompt=body.message, app=app,
                        conversation_id=body.conversation_id)
    return {
        "conversation_id": r.conversation_id,
        "user_message": MessageOut.model_validate(db.get(Message, r.user_message_id)),
        "message": MessageOut.model_validate(db.get(Message, r.assistant_message_id)),
        "decision": {"request_id": r.request_id, "input_action": r.input_action.value,
                     "output_action": r.output_action.value if r.output_action else None, "trust_status": r.trust_status,
                     "llm_called": r.llm_called, "review_case_id": r.review_case_id, "latency_ms": r.latency_ms},
    }


def _summary(conv: Conversation) -> dict:
    assistant_msgs = [m for m in conv.messages if m.role == "assistant"]
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at, "updated_at": conv.updated_at,
            "last_trust_status": assistant_msgs[-1].trust_status if assistant_msgs else None,
            "pending_reviews": sum(1 for m in assistant_msgs if m.status == "pending_review")}


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(user: User = Depends(use_assistant), db: Session = Depends(get_db)) -> list[dict]:
    convs = db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).limit(100))
    return [_summary(c) for c in convs]


def _own_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise NotFound("Conversation")
    return conv


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(conversation_id: int, user: User = Depends(use_assistant), db: Session = Depends(get_db)) -> dict:
    conv = _own_conversation(db, user, conversation_id)
    return {**_summary(conv), "messages": conv.messages}


@router.get("/messages/{message_id}/sources")
def message_sources(message_id: int, user: User = Depends(use_assistant), db: Session = Depends(get_db)) -> dict:
    msg = db.get(Message, message_id)
    if msg is None:
        raise NotFound("Message")
    _own_conversation(db, user, msg.conversation_id)
    return {"message_id": msg.id, "trust_status": msg.trust_status, "sources": msg.citations or []}
