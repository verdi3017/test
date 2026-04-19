from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock

import clickhouse_connect

from app.core.config import settings


class ClickHouseStore:
    def __init__(self) -> None:
        self.client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
        )
        self._lock = Lock()
        self._snapshot_buffer: list[tuple] = []
        self._signal_buffer: list[tuple] = []

    def ensure_schema(self) -> None:
        self.client.command(f"CREATE DATABASE IF NOT EXISTS {settings.clickhouse_database}")
        self.client.command(
            """
            CREATE TABLE IF NOT EXISTS orderbook_levels (
              ts DateTime64(3, 'UTC'),
              symbol LowCardinality(String),
              side Enum8('bid' = 1, 'ask' = 2),
              price Float64,
              volume Float64
            )
            ENGINE = MergeTree
            PARTITION BY toDate(ts)
            ORDER BY (symbol, ts, side, price)
            TTL ts + INTERVAL 5 DAY
            SETTINGS index_granularity = 8192
            """
        )
        self.client.command(
            """
            CREATE TABLE IF NOT EXISTS signals (
              ts DateTime64(3, 'UTC'),
              symbol LowCardinality(String),
              signal_type LowCardinality(String),
              side Nullable(LowCardinality(String)),
              price Nullable(Float64),
              score Float64,
              details String
            )
            ENGINE = MergeTree
            PARTITION BY toDate(ts)
            ORDER BY (symbol, ts, signal_type)
            TTL ts + INTERVAL 5 DAY
            """
        )

    def buffer_snapshot_levels(self, rows: list[tuple]) -> None:
        with self._lock:
            self._snapshot_buffer.extend(rows)
            if len(self._snapshot_buffer) >= settings.batch_size:
                self._flush_snapshots_locked()

    def buffer_signal_rows(self, rows: list[tuple]) -> None:
        with self._lock:
            self._signal_buffer.extend(rows)
            if len(self._signal_buffer) >= settings.batch_size:
                self._flush_signals_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_snapshots_locked()
            self._flush_signals_locked()

    def _flush_snapshots_locked(self) -> None:
        if not self._snapshot_buffer:
            return
        self.client.insert(
            "orderbook_levels",
            self._snapshot_buffer,
            column_names=["ts", "symbol", "side", "price", "volume"],
        )
        self._snapshot_buffer.clear()

    def _flush_signals_locked(self) -> None:
        if not self._signal_buffer:
            return
        self.client.insert(
            "signals",
            self._signal_buffer,
            column_names=["ts", "symbol", "signal_type", "side", "price", "score", "details"],
        )
        self._signal_buffer.clear()

    def query_history(self, symbol: str, minutes: int = 60) -> list[dict]:
        start = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = self.client.query(
            """
            SELECT ts, side, price, volume
            FROM orderbook_levels
            WHERE symbol = %(symbol)s AND ts >= %(start)s
            ORDER BY ts DESC
            LIMIT 20000
            """,
            parameters={"symbol": symbol, "start": start},
        )
        return [
            {"ts": row[0], "side": row[1], "price": row[2], "volume": row[3]}
            for row in result.result_rows
        ]

    def query_recent_signals(self, symbol: str, limit: int = 200) -> list[dict]:
        result = self.client.query(
            """
            SELECT ts, symbol, signal_type, side, price, score, details
            FROM signals
            WHERE symbol = %(symbol)s
            ORDER BY ts DESC
            LIMIT %(limit)s
            """,
            parameters={"symbol": symbol, "limit": limit},
        )
        return [
            {
                "ts": row[0],
                "symbol": row[1],
                "signal_type": row[2],
                "side": row[3],
                "price": row[4],
                "score": row[5],
                "details": row[6],
            }
            for row in result.result_rows
        ]
