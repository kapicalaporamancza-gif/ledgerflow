"""Thin facade over the AI provider. Keeps callers free of provider imports."""
from __future__ import annotations

from typing import Any

from app.providers.ai import get_ai_provider
from app.schemas.ai import Classification, DraftReply, Summary


class AIService:
    def __init__(self) -> None:
        self._p = get_ai_provider()

    async def classify(self, text: str, sender: str, subject: str) -> Classification:
        return await self._p.classify(text, sender=sender, subject=subject)

    async def summarize(self, text: str) -> Summary:
        return await self._p.summarize(text)

    async def draft_reply(self, context: dict[str, Any]) -> DraftReply:
        return await self._p.draft_reply(context)