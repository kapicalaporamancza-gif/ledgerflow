"""Mail provider facade."""
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
        paths: list[Path] = []
        target = settings.upload_dir / email_id
        target.mkdir(parents=True, exist_ok=True)

        for att in msg.attachments:
            # Keep filenames local to the message directory. Gmail and the mock
            # provider both use the same download interface here.
            safe = att.filename.replace("/", "_").replace("\\", "_")
            dest = target / safe

            if att.content:
                dest.write_bytes(att.content)
                paths.append(dest)
                continue

            if att.attachment_id:
                content = await self._p.download_attachment(
                    msg.external_id,
                    att.attachment_id,
                )
                dest.write_bytes(content)
                paths.append(dest)
            else:
                log.warning("Skipping attachment without content or attachment_id: %s", att.filename)

        return paths
