"""Builds a draft reply for a client/period pair. Never sends mail."""
from __future__ import annotations

from app.services.ai_service import AIService
from app.services.ledger_service import LedgerService


class ReplyService:
    def __init__(
        self,
        ai: AIService,
        ledger: LedgerService,
    ) -> None:
        self._ai = ai
        self._ledger = ledger

    async def draft(
        self,
        client_id: str,
        client_name: str,
        period: str,
    ) -> str:
        received = await self._ledger.received_for_period(client_id, period)
        missing = await self._ledger.find_missing(client_id, period)
        body = await self._ai.draft_reply(
            {
                "client_name": client_name,
                "period": period,
                "missing": missing,
                "received": received,
            }
        )
        return body.body