from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models.schemas import Signal, SnapshotResponse

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_ingestion(request: Request):
    return request.app.state.ingestion


def get_store(request: Request):
    return request.app.state.store


@router.get("/orderbook/snapshot", response_model=SnapshotResponse)
def snapshot(ingestion=Depends(get_ingestion)):
    snap = ingestion.current_snapshot()
    if not snap["mid_price"]:
        snap["mid_price"] = 0.0
    return snap


@router.get("/orderbook/history")
def history(
    symbol: str = Query(...),
    minutes: int = Query(60, ge=1, le=60 * 24 * 4),
    store=Depends(get_store),
):
    return store.query_history(symbol=symbol, minutes=minutes)


@router.get("/signals", response_model=list[Signal])
def signals(symbol: str = Query(...), limit: int = Query(200, ge=1, le=2000), store=Depends(get_store)):
    rows = store.query_recent_signals(symbol=symbol, limit=limit)
    out = []
    for row in rows:
        if isinstance(row["details"], str):
            import json

            row["details"] = json.loads(row["details"] or "{}")
        if isinstance(row["ts"], str):
            row["ts"] = datetime.fromisoformat(row["ts"])
        out.append(row)
    return out


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
