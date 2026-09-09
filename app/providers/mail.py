"""Mail provider abstraction. Mock returns deterministic demo data;
real implementation talks to Gmail API."""
from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.utils import parseaddr
from googleapiclient.discovery import build
import base64

from app.config import settings


@dataclass
class IncomingAttachment:
    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"
    attachment_id: str | None = None


@dataclass
class IncomingMessage:
    external_id: str
    sender: str
    subject: str
    body: str
    received_at: str  # ISO
    attachments: list[IncomingAttachment] = field(default_factory=list)


class MailProvider(ABC):
    @abstractmethod
    async def fetch_message(self, message_id: str) -> IncomingMessage: ...

    @abstractmethod
    async def list_recent(self, max_results: int = 20) -> list[IncomingMessage]: ...


# ----- mock ---------------------------------------------------------------

_DEMO = [
    {
        "sender": "biuro@abctransport.pl",
        "subject": "Dokumenty sierpien",
        "body": "Przesylam wyciag bankowy i leasing za sierpien 2026.",
        "files": [
            ("wyciag.pdf", b"[Mock PDF] Wyciag bankowy ABC Transport 2026-08"),
            ("leasing.pdf", b"[Mock PDF] Umowa leasingu ABC Transport"),
        ],
    },
    {
        "sender": "kontakt@janex.com.pl",
        "subject": "Faktury sierpien",
        "body": "W zalaczeniu faktury sprzedazy za sierpien.",
        "files": [
            ("faktury.zip", b"[Mock ZIP] Faktury sprzedazy Janex 2026-08"),
        ],
    },
    {
        "sender": "biuro@kowalski.pl",
        "subject": "Raport kasowy - sierpien",
        "body": "Przesylam raport kasowy za sierpien.",
        "files": [
            ("raport_kasowy.pdf", b"[Mock PDF] Raport kasowy Kowalski 2026-08"),
        ],
    },
]


class MockMailProvider(MailProvider):
    """Returns a deterministic, in-memory inbox for local demo / tests."""

    async def fetch_message(self, message_id: str) -> IncomingMessage:
        for i, m in enumerate(_DEMO):
            if message_id == f"mock-{i}":
                return _to_message(i, m)
        raise KeyError(message_id)

    async def list_recent(self, max_results: int = 20) -> list[IncomingMessage]:
        return [_to_message(i, m) for i, m in enumerate(_DEMO[:max_results])]


def _to_message(idx: int, raw: dict) -> IncomingMessage:
    return IncomingMessage(
        external_id=f"mock-{idx}",
        sender=raw["sender"],
        subject=raw["subject"],
        body=raw["body"],
        received_at="2026-08-31T09:00:00+00:00",
        attachments=[
            IncomingAttachment(filename=name, content=data, mime_type="application/pdf")
            for name, data in raw["files"]
        ],
    )


# ----- gmail --------------------------------------------------------------

class GmailProvider(MailProvider):
    """Real Gmail API implementation. Auth: OAuth2 with refresh token."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str) -> None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build  # noqa: F401

        self._creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
            ],
        )
        self._service = None  # lazy build

    def _svc(self):
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("gmail", "v1", credentials=self._creds, cache_discovery=False)
        return self._service

    async def fetch_message(self, message_id: str) -> IncomingMessage:
        def _do() -> IncomingMessage:
            svc = self._svc()
            msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            return _parse_gmail(msg)
        return await asyncio.to_thread(_do)
    
    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        def _do():
            svc = self._svc()
            att = (
                svc.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
            return base64.urlsafe_b64decode(att["data"])

        return await asyncio.to_thread(_do)

    async def list_recent(self, max_results: int = 20) -> list[IncomingMessage]:
        def _do() -> list[IncomingMessage]:
            svc = self._svc()
            listing = (
                svc.users()
                .messages()
                .list(userId="me", maxResults=max_results, q="has:attachment newer_than:7d")
                .execute()
            )
            out: list[IncomingMessage] = []
            for ref in listing.get("messages", []):
                msg = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
                out.append(_parse_gmail(msg))
            return out
        return await asyncio.to_thread(_do)


def _parse_gmail(msg: dict) -> IncomingMessage:
    """Parse Gmail message into IncomingMessage."""
    import base64

    headers = {
        h["name"].lower(): h["value"]
        for h in msg.get("payload", {}).get("headers", [])
    }

    raw_from = headers.get("from", "")
    _, sender = parseaddr(raw_from)

    subject = headers.get("subject", "")
    external_id = msg.get("id", "") or str(uuid.uuid4())

    body = ""
    attachments: list[IncomingAttachment] = []

    def walk(part: dict):
        nonlocal body

        mime = part.get("mimeType", "")
        filename = part.get("filename") or ""
        part_body = part.get("body", {})

        # Treść maila
        if mime == "text/plain" and "data" in part_body:
            body += base64.urlsafe_b64decode(
                part_body["data"] + "=="
            ).decode("utf-8", errors="ignore")

        # Załącznik
        if filename and "attachmentId" in part_body:
            attachments.append(
                IncomingAttachment(
                    filename=filename,
                    content=b"",
                    mime_type=mime,
                    attachment_id=part_body["attachmentId"],
                )
            )

        for child in part.get("parts", []) or []:
            walk(child)

    walk(msg.get("payload", {}))

    return IncomingMessage(
        external_id=external_id,
        sender=sender.lower(),
        subject=subject,
        body=body,
        received_at=headers.get("date", ""),
        attachments=attachments,
    )


# ----- factory ------------------------------------------------------------

_provider: MailProvider | None = None


def get_mail_provider() -> MailProvider:
    global _provider
    if _provider is not None:
        return _provider
    if (
        settings.mail_provider == "gmail"
        and settings.google_client_id
        and settings.google_client_secret
        and settings.google_refresh_token
    ):
        _provider = GmailProvider(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
    else:
        _provider = MockMailProvider()
    return _provider  # type: ignore[name-defined]