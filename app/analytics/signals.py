from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from app.ingestion.orderbook import OrderBookState


@dataclass
class SignalsEngine:
    wall_multiplier: float = 4.0
    removal_threshold: float = 0.6
    imbalance_threshold: float = 0.2
    spoof_window_seconds: int = 10

    def __post_init__(self) -> None:
        self._last_levels: dict[tuple[str, str, float], tuple[datetime, float]] = {}

    def evaluate(self, ob: OrderBookState) -> list[dict]:
        bids, asks = ob.depth_10pct()
        if not bids and not asks:
            return []

        ts = ob.ts
        symbol = ob.symbol
        out: list[dict] = []

        bid_volumes = [v for _, v in bids]
        ask_volumes = [v for _, v in asks]
        avg_bid = sum(bid_volumes) / len(bid_volumes) if bid_volumes else 0.0
        avg_ask = sum(ask_volumes) / len(ask_volumes) if ask_volumes else 0.0

        for side, levels, avg in (("bid", bids, avg_bid), ("ask", asks, avg_ask)):
            if avg <= 0:
                continue
            for price, volume in levels:
                key = (symbol, side, price)
                prev = self._last_levels.get(key)
                self._last_levels[key] = (ts, volume)

                if volume >= avg * self.wall_multiplier:
                    out.append(
                        {
                            "ts": ts,
                            "symbol": symbol,
                            "signal_type": "liquidity_wall",
                            "side": side,
                            "price": price,
                            "score": volume / avg,
                            "details": {"avg_volume": avg, "level_volume": volume},
                        }
                    )

                if prev:
                    prev_ts, prev_vol = prev
                    if prev_vol > 0 and volume < prev_vol * (1 - self.removal_threshold):
                        out.append(
                            {
                                "ts": ts,
                                "symbol": symbol,
                                "signal_type": "order_removal",
                                "side": side,
                                "price": price,
                                "score": (prev_vol - volume) / prev_vol,
                                "details": {"previous": prev_vol, "current": volume},
                            }
                        )

                        age = (ts - prev_ts).total_seconds()
                        if age <= self.spoof_window_seconds and prev_vol >= avg * self.wall_multiplier:
                            out.append(
                                {
                                    "ts": ts,
                                    "symbol": symbol,
                                    "signal_type": "potential_spoofing",
                                    "side": side,
                                    "price": price,
                                    "score": max((prev_vol - volume) / max(prev_vol, 1e-9), 0.0),
                                    "details": {
                                        "wall_before": prev_vol,
                                        "volume_after": volume,
                                        "seconds_active": age,
                                    },
                                }
                            )

        total_bid = sum(bid_volumes)
        total_ask = sum(ask_volumes)
        if total_bid + total_ask > 0:
            imbalance = (total_bid - total_ask) / (total_bid + total_ask)
            if abs(imbalance) >= self.imbalance_threshold:
                out.append(
                    {
                        "ts": ts,
                        "symbol": symbol,
                        "signal_type": "bid_ask_imbalance",
                        "side": "bid" if imbalance > 0 else "ask",
                        "price": ob.mid_price,
                        "score": abs(imbalance),
                        "details": {"total_bid": total_bid, "total_ask": total_ask, "imbalance": imbalance},
                    }
                )
        return out

    @staticmethod
    def serialize(signal: dict) -> tuple:
        return (
            signal["ts"],
            signal["symbol"],
            signal["signal_type"],
            signal.get("side"),
            signal.get("price"),
            signal["score"],
            json.dumps(signal.get("details", {})),
        )
