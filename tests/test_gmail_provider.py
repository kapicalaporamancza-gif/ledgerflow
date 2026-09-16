"""Tests for Gmail resilience and the shared attachment interface."""
from __future__ import annotations

import os
from pathlib import Path

# Keep the settings singleton isolated from any real .env values during tests.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_ledgerflow.db"
os.environ["AI_PROVIDER"] = "mock"
os.environ["MAIL_PROVIDER"] = "mock"
os.environ["OCR_PROVIDER"] = "mock"

from pathlib import Path

from google.auth.exceptions import RefreshError

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.config import settings
from app.providers.mail import (
    GmailAuthError,
    GmailProvider,
    IncomingAttachment,
    IncomingMessage,
)
from app.services.gmail_service import GmailService


class FakeRequest:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def execute(self):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_gmail_retries_transient_http_error(monkeypatch):
    provider = GmailProvider("client-id", "client-secret", "refresh-token")
    request = FakeRequest([
        HttpError(Response({"status": "503", "Retry-After": "1"}), b"busy"),
        "ok",
    ])
    sleeps: list[float] = []
    monkeypatch.setattr("app.providers.mail.time.sleep", sleeps.append)
    monkeypatch.setattr("app.providers.mail._retry_delay", lambda _attempt, _error: 1.0)

    assert provider._execute(request) == "ok"
    assert request.calls == 2
    assert sleeps == [1.0]


def test_gmail_does_not_retry_invalid_oauth_token():
    provider = GmailProvider("client-id", "client-secret", "refresh-token")
    request = FakeRequest([RefreshError("invalid_grant: token was revoked")])

    with pytest.raises(GmailAuthError, match="invalid_grant"):
        provider._execute(request)

    assert request.calls == 1


@pytest.mark.asyncio
async def test_attachment_download_uses_provider_interface(monkeypatch, tmp_path: Path):
    class FakeProvider:
        async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
            assert message_id == "message-1"
            assert attachment_id == "attachment-1"
            return b"PDF"

    monkeypatch.setattr("app.services.gmail_service.get_mail_provider", lambda: FakeProvider())
    message = IncomingMessage(
        external_id="message-1",
        sender="office@example.com",
        subject="Invoice",
        body="",
        received_at="2026-09-01T00:00:00+00:00",
        attachments=[
            IncomingAttachment(
                filename="invoice.pdf",
                content=b"",
                attachment_id="attachment-1",
            )
        ],
    )

    paths = await GmailService().save_attachments(message, "email-1")

    assert len(paths) == 1
    assert paths[0].read_bytes() == b"PDF"


def test_settings_use_project_relative_paths():
    assert settings.upload_dir.is_absolute()
    assert settings.gmail_lookback_days == 30
