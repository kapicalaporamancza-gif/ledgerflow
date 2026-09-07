"""Gmail webhook + ingestion pipeline.

POST /api/gmail/webhook receives an incoming message, persists it,
downloads attachments, classifies them via AI, assigns a client, and
updates the checklist. Designed so the same flow can be driven from
Gmail Pub/Sub, Outlook Graph, or our mock provider.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.document import Document
from app.models.email import Email
from app.providers.mail import get_mail_provider
from app.services.ai_service import AIService
from app.services.gmail_service import GmailService
from app.services.ledger_service import LedgerService, normalize_period
from app.services.pdf_service import PDFService

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gmail", tags=["gmail"])


class WebhookPayload(BaseModel):
    """Minimal payload for incoming webhooks. The actual provider may post
    richer data; we keep the contract narrow."""

    message_id: str


# ---------- background processing -----------------------------------------

async def process_message(message_id: str, external_id: str | None = None) -> None:
    """Full ingestion pipeline for one message."""
    mail = get_mail_provider()
    # We need a fresh session in the background task.
    from app.db import SessionLocal

    async with SessionLocal() as session:
        try:
            try:
                msg = await mail.fetch_message(message_id)
            except KeyError:
                log.warning("Unknown message_id %s", message_id)
                return

            pdf_svc = PDFService()
            ai_svc = AIService()
            gmail_svc = GmailService()

            # Persist email if not already.
            existing = None
            if msg.external_id:
                from sqlalchemy import select

                existing = (
                    await session.execute(
                        select(Email).where(Email.external_id == msg.external_id)
                    )
                ).scalar_one_or_none()
            email = existing or Email(
                sender=msg.sender,
                subject=msg.subject,
                body=msg.body,
                external_id=msg.external_id,
                status="processing",
            )
            if not existing:
                session.add(email)
            await session.flush()  # need email.id

            # Save attachments to disk.
            paths = await gmail_svc.save_attachments(msg, str(email.id))

            # Persist a Document row per attachment.
            ledger = LedgerService(session)
            for path in paths:
                text = await pdf_svc.extract_text(path)
                classification = await ai_svc.classify(
                    text=text, sender=msg.sender, subject=msg.subject or ""
                )
                client = await ledger.assign_client(
                    sender=msg.sender,
                    classified_name=classification.client_name,
                    text=text,
                )
                period = normalize_period(classification.period) or email.period

                doc = Document(
                    email_id=email.id,
                    client_id=client.id if client else None,
                    type=classification.document_type,
                    period=period,
                    confidence=classification.confidence,
                    filename=path.name,
                    storage_path=str(path),
                    json_data={
                        "raw_text": text[:4000],
                        "ai": classification.model_dump(),
                    },
                )
                session.add(doc)

            # Assign email-level client + period from first matched doc.
            await session.flush()
            from sqlalchemy import select as _sel

            doc_row = (
                await session.execute(
                    _sel(Document).where(Document.email_id == email.id).limit(1)
                )
            ).scalar_one_or_none()
            if doc_row and doc_row.client_id and not email.client_id:
                email.client_id = doc_row.client_id
            if doc_row and doc_row.period and not email.period:
                email.period = doc_row.period

            # Manual review if no client resolved.
            if not email.client_id:
                email.status = "manual_review"
            else:
                email.status = "done"

            # AI summary for the email itself.
            summary = await ai_svc.summarize(msg.body or "")
            email.ai_summary = summary.summary

            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("process_message failed: %s", message_id)
            raise


# ---------- routes ---------------------------------------------------------

@router.post("/webhook")
async def webhook(
    payload: WebhookPayload,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Ingest one message by id. Returns 202 + the email id if we kicked
    off processing, or 200 with the existing record if we saw it before."""
    try:
        msg = await get_mail_provider().fetch_message(payload.message_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="message_id not found")

    # Quick insert so we always have a row even if AI fails.
    from sqlalchemy import select

    existing = (
        await session.execute(
            select(Email).where(Email.external_id == msg.external_id)
        )
    ).scalar_one_or_none()
    if existing:
        return {"status": "duplicate", "email_id": str(existing.id)}

    email = Email(
        sender=msg.sender,
        subject=msg.subject,
        body=msg.body,
        external_id=msg.external_id,
        status="processing",
    )
    session.add(email)
    await session.commit()
    background.add_task(process_message, payload.message_id, msg.external_id)
    return {"status": "accepted", "email_id": str(email.id)}


@router.post("/ingest-all")
async def ingest_all(
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Pull all messages from the mail provider. Demo endpoint."""
    msgs = await get_mail_provider().list_recent()
    accepted: list[str] = []
    from sqlalchemy import select

    for msg in msgs:
        existing = (
            await session.execute(
                select(Email).where(Email.external_id == msg.external_id)
            )
        ).scalar_one_or_none()
        if existing:
            continue
        email = Email(
            sender=msg.sender,
            subject=msg.subject,
            body=msg.body,
            external_id=msg.external_id,
            status="processing",
        )
        session.add(email)
        accepted.append(msg.external_id)
    await session.commit()

    # Kick off processing for newly accepted.
    for ext in accepted:
        background.add_task(process_message, ext)
    return {"accepted": accepted, "skipped": len(msgs) - len(accepted)}