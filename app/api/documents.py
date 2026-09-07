"""Document-level endpoints. List + delete (RODO)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.document import Document

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
async def list_documents(
    client_id: uuid.UUID | None = None,
    period: str | None = None,
    type: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Document)
    if client_id:
        stmt = stmt.where(Document.client_id == client_id)
    if period:
        stmt = stmt.where(Document.period == period)
    if type:
        stmt = stmt.where(Document.type == type)
    rows = (await session.execute(stmt.order_by(Document.created_at.desc()))).scalars().all()
    return [
        {
            "id": str(d.id),
            "email_id": str(d.email_id),
            "client_id": str(d.client_id) if d.client_id else None,
            "type": d.type,
            "period": d.period,
            "confidence": d.confidence,
            "filename": d.filename,
        }
        for d in rows
    ]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """RODO: permanently remove a document and its file."""
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc.storage_path:
        try:
            Path(doc.storage_path).unlink(missing_ok=True)
        except OSError:
            pass
    await session.delete(doc)
    await session.commit()
    return None