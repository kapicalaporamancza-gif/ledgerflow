"""Flash message utilities for session-based notifications."""
from __future__ import annotations

from typing import Optional

from fastapi import Request


def _get_session(request: Request) -> dict:
    """Safely get session dict from scope, creating if missing."""
    # Check scope directly to avoid triggering Starlette's session property assertion
    if "session" in request.scope:
        return request.scope["session"]
    # For tests without SessionMiddleware, create a fallback session dict
    request.scope["session"] = {}
    return request.scope["session"]


def flash(request: Request, message: str, category: str = "info") -> None:
    """Store a flash message in the session."""
    session = _get_session(request)
    if "flash" not in session:
        session["flash"] = []
    session["flash"].append({"message": message, "category": category})


def get_flash(request: Request) -> Optional[dict]:
    """Retrieve and clear the latest flash message."""
    session = _get_session(request)
    flashes = session.pop("flash", None)
    if flashes:
        return flashes[-1]
    return None