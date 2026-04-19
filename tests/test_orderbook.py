from datetime import datetime, timezone

from app.ingestion.orderbook import OrderBookState


def test_orderbook_snapshot_delta_and_depth_filter():
    ts = datetime.now(timezone.utc)
    ob = OrderBookState(symbol="BTCUSDT")
    ob.apply_snapshot(bids=[(100.0, 1.0), (99.0, 2.0)], asks=[(101.0, 1.5), (102.0, 2.5)], ts=ts)

    assert ob.best_bid == 100.0
    assert ob.best_ask == 101.0
    assert ob.mid_price == 100.5

    ob.apply_delta(bids=[(100.0, 0.0), (98.0, 3.0)], asks=[(102.0, 0.0), (103.0, 1.0)], ts=ts)
    assert 100.0 not in ob.bids
    assert ob.bids[98.0] == 3.0
    assert 102.0 not in ob.asks

    bids, asks = ob.depth_10pct()
    assert bids
    assert asks
