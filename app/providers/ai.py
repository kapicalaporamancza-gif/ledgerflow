"""AI provider abstraction. Mock + OpenAI implementations."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import settings
from app.schemas.ai import Classification, DraftReply, Summary


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class AIProvider(ABC):
    """Thin contract for any AI backend. Implementations must return
    validated Pydantic objects, never raw dicts."""

    @abstractmethod
    async def classify(self, text: str, sender: str, subject: str) -> Classification: ...

    @abstractmethod
    async def summarize(self, text: str) -> Summary: ...

    @abstractmethod
    async def draft_reply(self, context: dict[str, Any]) -> DraftReply: ...


# ----- shared helpers -----------------------------------------------------

def _strip_json(text: str) -> str:
    """OpenAI sometimes wraps JSON in ```json fences or prepends prose."""
    text = text.strip()
    # Remove code fences.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    # Grab from first { to last }.
    if "{" in text and "}" in text:
        text = text[text.find("{") : text.rfind("}") + 1]
    return text


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


# ----- mock ---------------------------------------------------------------

class MockAIProvider(AIProvider):
    """Deterministic, offline AI. Used in dev / tests so the pipeline runs
    without API keys. Heuristics match the demo data in mail_provider."""

    async def classify(self, text: str, sender: str, subject: str) -> Classification:
        blob = f"{text} {subject}".lower()
        sender_l = sender.lower()

        # Heuristic document_type detection. Use ASCII fallbacks so mock
        # bytes-only fixtures still classify correctly.
        if "wyci" in blob or "bank" in blob or "kasow" in blob or "raport_kasowy" in blob:
            doc_type = "bank_statement"
            conf = 0.97
        elif "faktur" in blob or "invoice" in blob or "vat" in blob:
            doc_type = "invoice"
            conf = 0.95
        elif "paragon" in blob or "receipt" in blob:
            doc_type = "receipt"
            conf = 0.93
        elif "leasing" in blob or "lease" in blob:
            doc_type = "lease"
            conf = 0.94
        elif "umowa" in blob or "contract" in blob:
            doc_type = "contract"
            conf = 0.9
        elif "payroll" in blob or "lista p" in blob:
            doc_type = "payroll"
            conf = 0.92
        else:
            doc_type = "other"
            conf = 0.4

        # Heuristic period: pull YYYY-MM out of subject or text, else None.
        period = None
        m = re.search(r"\b(20\d{2})-(\d{2})\b", blob)
        if m:
            period = f"{m.group(1)}-{m.group(2)}"
        else:
            months = {
                "stycz": "01", "luty": "02", "marzec": "03", "kwiec": "04",
                "maj": "05", "czerw": "06", "lipiec": "07", "sierp": "08",
                "wrzes": "09", "pazdz": "10", "listop": "11", "grudz": "12",
            }
            for name, num in months.items():
                if name in blob:
                    period = f"2026-{num}"
                    break

        # Heuristic client name: prefer email-localpart, fallback None.
        client_name = sender_l.split("@")[0].replace(".", " ").title() if sender_l else None

        return Classification(
            document_type=doc_type,  # type: ignore[arg-type]
            client_name=client_name,
            period=period,
            confidence=conf,
        )

    async def summarize(self, text: str) -> Summary:
        first = (text or "").strip().splitlines()
        short = " | ".join(first[:3])[:300] if first else ""
        return Summary(summary=short or "(brak treści)")

    async def draft_reply(self, context: dict[str, Any]) -> DraftReply:
        client = context.get("client_name", "Kliencie")
        missing: list[str] = context.get("missing", []) or []
        received: list[str] = context.get("received", []) or []
        period = context.get("period", "")
        pretty = {
            "invoice": "faktury",
            "bank_statement": "wyciągu bankowego",
            "receipt": "paragonów",
            "lease": "leasingu",
            "contract": "umowy",
            "payroll": "listy płac",
            "other": "innych dokumentów",
        }
        if missing:
            miss_text = ", ".join(pretty.get(m, m) for m in missing)
            body = (
                f"Dzień dobry,\n\ndziękujemy za przesłane dokumenty. "
                f"Do zamknięcia {period or 'bieżącego miesiąca'} brakuje jeszcze: {miss_text}.\n\n"
                f"Prosimy o uzupełnienie, gdy będzie to możliwe.\n\nPozdrawiam"
            )
        else:
            body = (
                f"Dzień dobry,\n\ndziękujemy za przesłane dokumenty ({', '.join(received) or 'komplet'}). "
                f"{period or 'Bieżący miesiąc'} jest kompletny — możemy przystąpić do rozliczenia.\n\nPozdrawiam"
            )
        return DraftReply(body=body)


# ----- openai -------------------------------------------------------------

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # lazy init

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def _json_call(self, system: str, user: str) -> dict[str, Any]:
        client = self._get_client()
        resp = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(_strip_json(content))

    async def classify(self, text: str, sender: str, subject: str) -> Classification:
        template = _load_prompt("classify.txt")
        user = template.format(document_text=text[:8000], sender=sender, subject=subject)
        try:
            data = await self._json_call(
                "You classify accounting documents. Return strict JSON only.",
                user,
            )
            return Classification.model_validate(data)
        except Exception:
            # Spec: validation failure -> document marked as "other".
            return Classification(document_type="other", confidence=0.0)

    async def summarize(self, text: str) -> Summary:
        try:
            data = await self._json_call(
                "Summarize the email in <= 280 chars. Return {\"summary\": str}.",
                text[:6000],
            )
            return Summary.model_validate(data)
        except Exception:
            return Summary(summary=(text or "")[:280])

    async def draft_reply(self, context: dict[str, Any]) -> DraftReply:
        template = _load_prompt("reply.txt")
        user = template.format(
            client_name=context.get("client_name", ""),
            period=context.get("period", ""),
            missing=", ".join(context.get("missing", []) or []),
            received=", ".join(context.get("received", []) or []),
        )
        try:
            data = await self._json_call(
                "Write the email body in Polish. Return {\"body\": str}.",
                user,
            )
            return DraftReply.model_validate(data)
        except Exception:
            return DraftReply(body="(nie udało się wygenerować szkicu)")


# ----- factory ------------------------------------------------------------

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    global _provider
    if _provider is not None:
        return _provider
    if settings.ai_provider == "openai" and settings.openai_api_key:
        _provider = OpenAIProvider(settings.openai_api_key, settings.openai_model)
    else:
        _provider = MockAIProvider()
    return _provider