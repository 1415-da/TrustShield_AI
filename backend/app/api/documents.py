from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import NotFound
from app.models import Document, User
from app.schemas.misc import DocumentDetail, DocumentOut
from app.services import audit, documents, retrieval
from app.workers import tasks

router = APIRouter(prefix="/admin/documents", tags=["documents"])
can_read = require_permission("documents:read")
can_write = require_permission("documents:write")


@router.post("", response_model=DocumentOut, status_code=202)
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    trust_level: str = Form("trusted"),
    user: User = Depends(can_write),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    text, content_type = documents.decode_upload(file.filename or "upload.txt", raw)
    name = title.strip() or (file.filename or "Untitled").rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    doc = documents.create_document(db, title=name, filename=file.filename or "upload.txt", content=text,
                                    content_type=content_type, trust_level=trust_level, user=user)
    audit.record(db, "document.uploaded", **audit.actor_fields(user), commit=True,
                 details={"document_id": doc.id, "title": doc.title, "bytes": len(raw), "trust_level": doc.trust_level},
                 content_hash=doc.content_hash)
    background.add_task(tasks.reindex_document, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(_: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document")
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, user: User = Depends(can_write), db: Session = Depends(get_db)) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document")
    audit.record(db, "document.deleted", **audit.actor_fields(user), details={"document_id": doc.id, "title": doc.title},
                 content_hash=doc.content_hash)
    db.delete(doc)
    db.commit()
    retrieval.invalidate()


@router.post("/{document_id}/reindex", response_model=DocumentOut, status_code=202)
def reindex(document_id: int, background: BackgroundTasks, user: User = Depends(can_write), db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document")
    doc.status = "processing"
    audit.record(db, "document.reindexed", **audit.actor_fields(user), details={"document_id": doc.id, "title": doc.title})
    db.commit()
    background.add_task(tasks.reindex_document, doc.id)
    return doc
