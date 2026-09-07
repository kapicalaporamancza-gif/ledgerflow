"""Dashboard page route. Logic in clients.dashboard for now."""
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Pages live in clients.py; this module exists to match the planned layout
# and to host dashboard-only endpoints (e.g. global stats) later on.