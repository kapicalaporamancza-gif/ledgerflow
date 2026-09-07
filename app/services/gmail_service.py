"""Mail provider facade (named gmail_service per the spec, despite working
with any MailProvider)."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.providers.mail import IncomingMessage, get_mail_provider

log = logging.getLogger(__name__)


class GmailService:
    def __init__(self) -> None:
        self._p = get_mail_provider()

    async def fetch_message(self, message_id: str) -> IncomingMessage:
        return await self._p.fetch_message(message_id)

    async def list_recent(self, max_results: int = 20) -> list[IncomingMessage]:
        return await self._p.list_recent(max_results)

    async def save_attachments(self, msg: IncomingMessage, email_id: str) -> list[Path]:
        """Persist attachment bytes to local disk. Returns paths."""
        paths: list[Path] = []
        target = settings.upload_dir / email_id
        target.mkdir(parents=True, exist_ok=True)
        for att in msg.attachments:
            if not att.content:
                continue
            safe = att.filename.replace("/", "_").replace("\\", "_")
            dest = target / safe
            dest.write_bytes(att.content)
            paths.append(dest)
        return paths