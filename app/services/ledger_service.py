"""Ledger / checklist logic: client assignment + missing-doc detection."""
from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Iterable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.client import Client
from app.models.document import Document
from app.models.email import Email


NIP_RE = re.compile(r"\b(\d{10})\b")


class LedgerService:
    """Coordinates client assignment and missing-doc detection."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- client assignment ----------------------------------------

    async def assign_client(
        self,
        sender: str,
        classified_name: str | None,
        text: str | None,
    ) -> Client | None:
        """Resolution order per spec: email -> NIP -> fuzzy name."""
        # 1) exact email match
        if sender:
            row = (
                await self.session.execute(
                    select(Client).where(func.lower(Client.email) == sender.lower().strip())
                )
            ).scalar_one_or_none()
            if row:
                return row

        # 2) NIP from text
        if text:
            m = NIP_RE.search(text)
            if m:
                nip = m.group(1)
                row = (
                    await self.session.execute(
                        select(Client).where(Client.tax_id == nip)
                    )
                ).scalar_one_or_none()
                if row:
                    return row

        # 3) fuzzy name
        if classified_name:
            clients = (await self.session.execute(select(Client))).scalars().all()
            best = self._best_match(classified_name, clients)
            if best and best[1] >= 0.7:
                return best[0]
        return None

    @staticmethod
    def _best_match(
        query: str, clients: Iterable[Client]
    ) -> tuple[Client, float] | None:
        best: tuple[Client, float] | None = None
        q = query.lower().strip()
        for c in clients:
            score = SequenceMatcher(None, q, c.name.lower().strip()).ratio()
            if best is None or score > best[1]:
                best = (c, score)
        return best

    # ---------- checklist --------------------------------------------------

    async def find_missing(self, client_id: str, period: str) -> list[str]:
        client = await self.session.get(Client, client_id)
        if not client:
            return []
        required = settings.required_docs_by_kind.get(client.kind, [])
        received = await self._received_types(client_id, period)
        return [d for d in required if d not in received]

    async def received_for_period(
        self, client_id: str, period: str
    ) -> list[str]:
        return list(await self._received_types(client_id, period))

    async def _received_types(self, client_id: str, period: str) -> set[str]:
        rows = (
            await self.session.execute(
                select(Document.type).where(
                    Document.client_id == _to_uuid(client_id),
                    Document.period == period,
                )
            )
        ).scalars().all()
        return {r for r in rows if r}

    # ---------- helpers ---------------------------------------------------

    async def update_checklist(self, client_id: str, period: str) -> list[str]:
        return await self.find_missing(client_id, period)


def _to_uuid(value: str):
    import uuid

    return uuid.UUID(str(value))


def period_now() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def normalize_period(value: str | None) -> str | None:
    """Accept 'YYYY-MM', 'YYYY-MM-DD' or None; return 'YYYY-MM'."""
    if not value:
        return None
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}$", value):
        return value
    m = re.match(r"^(\d{4})-(\d{2})-\d{2}$", value)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None