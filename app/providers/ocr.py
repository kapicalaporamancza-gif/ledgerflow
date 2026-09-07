"""OCR provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings


class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, file_path: str | Path) -> str: ...


class MockOCRProvider(OCRProvider):
    """Returns a hint string so the AI can still classify. Useful in tests."""

    def extract_text(self, file_path: str | Path) -> str:
        return (
            "[OCR mock] Brak warstwy tekstowej w PDF. "
            f"Plik: {Path(file_path).name}"
        )


class TesseractOCRProvider(OCRProvider):
    def extract_text(self, file_path: str | Path) -> str:
        import pytesseract
        from PIL import Image

        image = Image.open(file_path)
        return pytesseract.image_to_string(image, lang="pol+eng")


class MistralOCRProvider(OCRProvider):
    def __init__(self, api_key: str, endpoint: str) -> None:
        self._api_key = api_key
        self._endpoint = endpoint

    def extract_text(self, file_path: str | Path) -> str:
        import httpx

        with open(file_path, "rb") as f:
            files = {"document": (Path(file_path).name, f, "application/octet-stream")}
            headers = {"Authorization": f"Bearer {self._api_key}"}
            r = httpx.post(self._endpoint, files=files, headers=headers, timeout=60.0)
        r.raise_for_status()
        data = r.json()
        # Adapt to whatever Mistral returns; assume `text` or `pages[*].text`.
        if isinstance(data, dict) and "text" in data:
            return data["text"]
        if isinstance(data, dict) and "pages" in data:
            return "\n".join(p.get("text", "") for p in data["pages"])
        return str(data)


_provider: OCRProvider | None = None


def get_ocr_provider() -> OCRProvider:
    global _provider
    if _provider is not None:
        return _provider
    if settings.ocr_provider == "tesseract":
        _provider = TesseractOCRProvider()
    elif settings.ocr_provider == "mistral" and settings.mistral_api_key:
        _provider = MistralOCRProvider(settings.mistral_api_key, settings.mistral_ocr_endpoint)
    else:
        _provider = MockOCRProvider()
    return _provider