"""LedgerFlow — application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from app.api import clients as clients_api
from app.api import dashboard as dashboard_api
from app.api import documents as documents_api
from app.api import gmail as gmail_api
from app.config import settings
from app.db import init_db
from app.utils.flash import get_flash


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="LedgerFlow AI",
    version="0.1.0",
    description="Asystent obiegu dokumentów dla biura rachunkowego.",
    lifespan=lifespan,
)

# Session middleware for flash messages
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False)

# Make flash available in all templates
@app.middleware("http")
async def add_flash_to_request(request: Request, call_next):
    from app.utils.flash import get_flash
    request.state.flash = get_flash(request)
    response = await call_next(request)
    return response

# Routers
app.include_router(gmail_api.router)
app.include_router(clients_api.router)        # /api/clients/*
app.include_router(clients_api.pages)         # HTML pages
app.include_router(documents_api.router)
app.include_router(dashboard_api.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}