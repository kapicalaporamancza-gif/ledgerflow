# LedgerFlow AI — MVP

Asystent obiegu dokumentów dla biura rachunkowego.

Nie robi: księgowania, interpretacji podatkowej, wysyłki maili bez zgody.
Robi: pobiera maile → analizuje załączniki → rozpoznaje typ dokumentu →
przypisuje klienta → wykrywa brakujące dokumenty → tworzy szkic odpowiedzi.

## Stack

- **Backend**: FastAPI + SQLAlchemy 2 (async) + SQLite (dev) / Postgres (prod)
- **AI**: OpenAI Responses API (z mockiem offline do dev/testów)
- **PDF**: pdfplumber → OCR fallback (Tesseract lub Mistral OCR API)
- **Mail**: Gmail API (z mockiem demo)
- **Front**: Jinja2 + HTMX (zero build step)

## Szybki start

```bash
# 1) Wymagania: Python 3.12+
python --version

# 2) Venv + zależności
uv venv .venv --python 3.12
uv pip install -r requirements.txt

# 3) (opcjonalnie) skopiuj .env
cp .env.example .env

# 4) Migracja + serwer (DB tworzy się automatycznie)
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Otwórz: <http://localhost:8000/dashboard>

## Tryb demo (bez kluczy API)

Domyślnie `AI_PROVIDER=mock` i `MAIL_PROVIDER=mock`. Demo dostarcza
3 przykładowe maile (ABC Transport, Janex, Kowalski), z których
każdy ma załączniki i rozpoznawalny typ dokumentu.

Kliknij **Pobierz maile** w prawym górnym rogu, żeby je zaciągnąć.

## Włączenie prawdziwych providerów

Ustaw w `.env`:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

MAIL_PROVIDER=gmail
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

Abstrakcje w `app/providers/` (ai.py / mail.py / ocr.py) mają ten
sam interfejs dla mocka i prawdziwej implementacji — wystarczy zmiana
konfiguracji, żeby przełączyć.

## Struktura

```
ledgerflow/
├── app/
│   ├── main.py              # FastAPI + lifespan
│   ├── config.py            # pydantic-settings
│   ├── db.py                # async engine + Base
│   ├── models/              # Client, Email, Document
│   ├── schemas/ai.py        # Pydantic DTO + Classification
│   ├── providers/           # AI / Mail / OCR abstraction
│   ├── services/            # pdf / ai / gmail / ledger / reply
│   ├── api/                 # FastAPI routers
│   ├── prompts/             # classify.txt + reply.txt
│   └── templates/           # Jinja2 + HTMX
├── tests/test_smoke.py
├── requirements.txt
└── .env.example
```

## API (skrót)

| Metoda | Endpoint | Opis |
|---|---|---|
| `GET`  | `/api/clients` | Lista klientów + `missing` |
| `POST` | `/api/clients` | Dodaj klienta (form) |
| `GET`  | `/api/clients/{id}/documents?period=YYYY-MM` | Dokumenty klienta w miesiącu |
| `GET`  | `/api/clients/{id}/detail` | Kompozyt: docs + last email + draft |
| `GET`  | `/api/documents?client_id&period&type` | Filtrowalna lista |
| `DELETE` | `/api/documents/{id}` | RODO: trwałe usunięcie |
| `POST` | `/api/gmail/webhook` | Webhook Gmail (id wiadomości) |
| `POST` | `/api/gmail/ingest-all` | Demo: zaciąga mocka |
| `GET`  | `/dashboard` | UI: lista klientów |
| `GET`  | `/clients/{id}` | UI: szczegóły klienta + draft |

## Sprinty (zgodne ze specyfikacją)

- [x] **Sprint 1** — FastAPI + DB + modele + panel klientów
- [x] **Sprint 2** — integracja mail providera (mock + Gmail) + zapis maili + upload PDF
- [x] **Sprint 3** — parser PDF (pdfplumber + OCR fallback) + AI klasyfikacja (mock + OpenAI)
- [x] **Sprint 4** — checklista brakujących dokumentów + szkic odpowiedzi

## Testy

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

5 testów smoke (FastAPI + httpx ASGITransport) — bez zewnętrznych zależności.

## RODO

- Dane tylko w bazie klienta (UE; dla prod → Postgres w UE).
- OpenAI przez API biznesowe (nie ChatGPT).
- Logi **nie** zawierają treści dokumentów.
- `DELETE /api/documents/{id}` → trwałe usunięcie (DB + plik).
- Szkice odpowiedzi **nigdy** nie są wysyłane bez akceptacji użytkownika.

## Następne kroki (poza MVP)

- KSeF / Optima / enova integracja
- Outlook (Microsoft Graph) obok Gmaila
- BullMQ / Celery zamiast FastAPI BackgroundTasks
- Alembic zamiast `create_all`
- Auth (multi-tenant biuro rachunkowe)