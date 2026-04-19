from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.db.clickhouse import ClickHouseStore
from app.ingestion.metascalp_client import MetaScalpIngestionService

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="MetaScalp OrderBook MVP")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    store = ClickHouseStore()
    store.ensure_schema()
    ingestion = MetaScalpIngestionService(store)

    app.state.store = store
    app.state.ingestion = ingestion
    await ingestion.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.ingestion.stop()
