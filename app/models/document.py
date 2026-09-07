"""Document ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator

from app.db import Base
from app.models.client import GUID


class JSONBCompat(TypeDecorator):
    """Use native JSONB on Postgres, generic JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Must be one of DOCUMENT_TYPES.
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="other", index=True)
    # Period as ISO yyyy-mm; nullable if unknown.
    period: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Extracted fields (NIP, invoice number, totals, etc.) + raw AI response.
    json_data: Mapped[dict | None] = mapped_column(JSONBCompat(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )