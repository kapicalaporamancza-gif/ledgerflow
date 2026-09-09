"""Mail provider facade."""
from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path

from app.config import settings
from app.providers.mail import GmailProvider, IncomingMessage, get_mail_provider

log = logging.getLogger(__name__)


class GmailService:
    def __init__(self) -> None:
        self._p = get_mail_provider()

    async def fetch_message(self, message_id: str) -> IncomingMessage:
        return await self._p.fetch_message(message_id)

    async def list_recent(self, max_results: int = 20) -> list[IncomingMessage]:
        return await self._p.list_recent(max_results)

    async def save_attachments(self, msg: IncomingMessage, email_id: str) -> list[Path]:
        paths: list[Path] = []
        target = settings.upload_dir / email_id
        target.mkdir(parents=True, exist_ok=True)

        for att in msg.attachments:
            safe = att.filename.replace("/", "_").replace("\\", "_")
            dest = target / safe

            # MOCK -> zapisujemy od razu
            if att.content:
                dest.write_bytes(att.content)
                paths.append(dest)
                continue

            # GMAIL -> pobieramy prawdziwy plik
            if isinstance(self._p, GmailProvider) and att.attachment_id:
                def _download():
                    svc = self._p._svc()
                    data = (
                        svc.users()
                        .messages()
                        .attachments()
                        .get(
                            userId="me",
                            messageId=msg.external_id,
                            id=att.attachment_id,
                        )
                        .execute()
                    )
                    return base64.urlsafe_b64decode(data["data"])

                content = await asyncio.to_thread(_download)
                dest.write_bytes(content)
                paths.append(dest)

        return paths