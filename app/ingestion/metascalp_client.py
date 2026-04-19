from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime, timezone

import websockets

from app.analytics.signals import SignalsEngine
from app.core.config import settings
from app.db.clickhouse import ClickHouseStore
from app.ingestion.orderbook import OrderBookState

logger = logging.getLogger(__name__)


class MetaScalpIngestionService:
    def __init__(self, store: ClickHouseStore) -> None:
        self.store = store
        self.orderbook = OrderBookState(symbol=settings.metascalp_symbol)
        self.signals = SignalsEngine()
        self._task: asyncio.Task | None = None
        self._flush_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="metascalp-ws")
        self._flush_task = asyncio.create_task(self._periodic_flush(), name="ch-flush")

    async def stop(self) -> None:
        self._stop.set()
        for task in (self._task, self._flush_task):
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        self.store.flush()

    async def _periodic_flush(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(max(settings.snapshot_interval_ms / 1000.0, 0.2))
            self.store.flush()

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                async with websockets.connect(settings.metascalp_ws_url, ping_interval=20, ping_timeout=20) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "action": "subscribe",
                                "channel": "orderbook",
                                "symbol": settings.metascalp_symbol,
                            }
                        )
                    )
                    logger.info("Connected to MetaScalp WS and subscribed")
                    async for raw in ws:
                        if self._stop.is_set():
                            return
                        self._handle_message(raw)
            except Exception as exc:  # reconnect loop
                logger.warning("WS loop failed: %s", exc)
                await asyncio.sleep(1.0)

    def _handle_message(self, raw: str) -> None:
        payload = json.loads(raw)
        msg_type = payload.get("type")
        ts = datetime.fromtimestamp(payload.get("ts", datetime.now(tz=timezone.utc).timestamp()), tz=timezone.utc)

        bids = [(float(p), float(v)) for p, v in payload.get("bids", [])]
        asks = [(float(p), float(v)) for p, v in payload.get("asks", [])]

        if msg_type == "snapshot":
            self.orderbook.apply_snapshot(bids, asks, ts)
        elif msg_type == "delta":
            self.orderbook.apply_delta(bids, asks, ts)
        else:
            return

        depth_bids, depth_asks = self.orderbook.depth_10pct()
        rows = [
            (ts, self.orderbook.symbol, "bid", price, volume)
            for price, volume in depth_bids
        ] + [
            (ts, self.orderbook.symbol, "ask", price, volume)
            for price, volume in depth_asks
        ]
        if rows:
            self.store.buffer_snapshot_levels(rows)

        detected = self.signals.evaluate(self.orderbook)
        if detected:
            self.store.buffer_signal_rows([self.signals.serialize(s) for s in detected])

    def current_snapshot(self) -> dict:
        bids, asks = self.orderbook.depth_10pct()
        return {
            "symbol": self.orderbook.symbol,
            "ts": self.orderbook.ts,
            "mid_price": self.orderbook.mid_price,
            "bids": [{"price": p, "volume": v} for p, v in bids],
            "asks": [{"price": p, "volume": v} for p, v in asks],
        }
