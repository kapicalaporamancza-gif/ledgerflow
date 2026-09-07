"""PDF text extraction. Falls back to OCR if no text layer."""
from __future__ import annotations

import logging
from pathlib import Path

from app.providers.ocr import get_ocr_provider

log = logging.getLogger(__name__)


class PDFService:
    """Extract text from a PDF file. Async-friendly wrapper."""

    async def extract_text(self, path: str | Path) -> str:
        path = Path(path)
        text = await self._try_pdfplumber(path)
        if text and len(text.strip()) >= 20:
            return text
        # Fallback to OCR if PDF is scanned.
        try:
            ocr_text = get_ocr_provider().extract_text(path)
            return ocr_text or ""
        except Exception as e:  # pragma: no cover - defensive
            log.warning("OCR failed for %s: %s", path, e)
            return text or ""

    async def _try_pdfplumber(self, path: Path) -> str:
        try:
            import pdfplumber
        except Exception:  # pragma: no cover - optional dep
            return ""

        def _open() -> str:
            chunks: list[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            return "\n".join(chunks)

        # pdfplumber is sync; run in a thread to keep the API async.
        import asyncio

        try:
            return await asyncio.to_thread(_open)
        except Exception:
            # Not a real PDF (or corrupted) -> let OCR / caller decide.
            return ""