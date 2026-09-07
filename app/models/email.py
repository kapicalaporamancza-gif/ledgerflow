"""Email ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.client import GUID


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sender: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # new | processing | manual_review | done
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Period this email is associated with (e.g. "2026-08"). Best-effort.
    period: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)
    # Provider message id for idempotent ingestion.
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    def __repr__(self) -> str:
        return f"<Email {self.sender} - {self.subject}>"