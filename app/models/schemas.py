from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Side = Literal["bid", "ask"]


class PriceLevel(BaseModel):
    price: float
    volume: float


class MetaScalpMessage(BaseModel):
    type: Literal["snapshot", "delta"]
    symbol: str
    ts: datetime
    bids: list[PriceLevel] = Field(default_factory=list)
    asks: list[PriceLevel] = Field(default_factory=list)


class SnapshotResponse(BaseModel):
    symbol: str
    ts: datetime
    mid_price: float
    bids: list[PriceLevel]
    asks: list[PriceLevel]


class HistoryRow(BaseModel):
    ts: datetime
    side: Side
    price: float
    volume: float


class Signal(BaseModel):
    ts: datetime
    symbol: str
    signal_type: str
    side: Side | None = None
    price: float | None = None
    score: float
    details: dict
