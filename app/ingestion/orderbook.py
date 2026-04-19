from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class OrderBookState:
    symbol: str
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def apply_snapshot(self, bids: list[tuple[float, float]], asks: list[tuple[float, float]], ts: datetime) -> None:
        self.bids = {p: v for p, v in bids if v > 0}
        self.asks = {p: v for p, v in asks if v > 0}
        self.ts = ts

    def apply_delta(self, bids: list[tuple[float, float]], asks: list[tuple[float, float]], ts: datetime) -> None:
        for p, v in bids:
            if v <= 0:
                self.bids.pop(p, None)
            else:
                self.bids[p] = v
        for p, v in asks:
            if v <= 0:
                self.asks.pop(p, None)
            else:
                self.asks[p] = v
        self.ts = ts

    @property
    def best_bid(self) -> float | None:
        return max(self.bids) if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return min(self.asks) if self.asks else None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    def depth_10pct(self) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        mid = self.mid_price
        if mid is None:
            return [], []

        low = mid * 0.9
        high = mid * 1.1

        bids = sorted(((p, v) for p, v in self.bids.items() if low <= p <= high), reverse=True)
        asks = sorted((p, v) for p, v in self.asks.items() if low <= p <= high)
        return bids, asks
