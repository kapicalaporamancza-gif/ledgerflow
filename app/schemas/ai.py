"""Pydantic schemas for AI inputs/outputs and API DTOs."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


# ---------- AI ----------

DocumentType = Literal[
    "invoice",
    "bank_statement",
    "receipt",
    "lease",
    "contract",
    "payroll",
    "other",
]

DOCUMENT_TYPES: list[str] = [
    "invoice",
    "bank_statement",
    "receipt",
    "lease",
    "contract",
    "payroll",
    "other",
]


class Classification(BaseModel):
    """Strict shape of one AI classification response."""

    document_type: DocumentType = "other"
    client_name: str | None = None
    period: str | None = Field(default=None, description="ISO yyyy-mm or yyyy-mm-dd")
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class Summary(BaseModel):
    summary: str


class DraftReply(BaseModel):
    body: str = Field(max_length=2000)


# ---------- API DTOs ----------

class ClientCreate(BaseModel):
    name: str
    email: str | None = None
    tax_id: str | None = None
    kind: Literal["company", "sole_prop"] = "company"
    notes: str | None = None


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    tax_id: str | None
    kind: str
    missing: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: uuid.UUID
    type: str
    period: str | None
    confidence: float
    filename: str | None

    model_config = {"from_attributes": True}


class EmailOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID | None
    sender: str
    subject: str | None
    status: str
    period: str | None
    received_at: str
    documents: list[DocumentOut] = Field(default_factory=list)


class ClientDetail(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    tax_id: str | None
    kind: str
    period: str
    received: list[str]
    missing: list[str]
    last_email: EmailOut | None
    draft_reply: str | None