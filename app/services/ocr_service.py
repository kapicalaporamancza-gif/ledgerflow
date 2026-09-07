"""OCR facade. Real engine chosen via config."""
from __future__ import annotations

from pathlib import Path

from app.providers.ocr import get_ocr_provider


class OCRService:
    def extract(self, file_path: str | Path) -> str:
        return get_ocr_provider().extract_text(file_path)