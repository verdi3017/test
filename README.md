# MetaScalp Order Book Analytics MVP

This MVP ingests MetaScalp local order book data, reconstructs full state in memory, stores ±10% depth to ClickHouse, computes market microstructure signals, and serves REST + a basic dashboard.

## Step-by-step execution plan (explained first)

1. **Connect to MetaScalp WebSocket**
   - Establish a resilient WS loop to `ws://127.0.0.1:PORT`.
   - Send `subscribe` command for order book stream.
   - Reconnect on failure with short backoff.

2. **Parse order book messages**
   - Handle two message types:
     - `snapshot`: full book reset
     - `delta`: partial level updates
   - Normalize into numeric `(price, volume)` tuples and a UTC timestamp.

3. **Build in-memory order book**
   - Maintain two maps: `bids` and `asks` keyed by price.
   - On `snapshot`, replace all levels.
   - On `delta`, upsert levels; remove when volume `<= 0`.
   - Compute `best_bid`, `best_ask`, `mid_price`.
   - Keep only ±10% depth around `mid_price` for storage and analysis.

4. **Store snapshots**
   - Use ClickHouse MergeTree table `orderbook_levels`.
   - Write every filtered level with `(ts, symbol, side, price, volume)`.
   - Buffer inserts in memory and flush in batches + periodic timer to reduce write overhead and data loss risk.
   - Apply 5-day TTL to support 3–4 days history comfortably.

5. **Build API**
   - `GET /orderbook/snapshot`: latest in-memory filtered book.
   - `GET /orderbook/history`: queried levels from ClickHouse for configurable window.
   - `GET /signals`: latest detected events.

6. **Add basic visualization**
   - Single-page dashboard with:
     - bid/ask depth bars
     - heatmap-like intensity chart
     - replay list for detected signals

## Signal detection in MVP

- **Large liquidity walls**: level volume vs rolling side average (multiplier threshold).
- **Sudden removal**: quick drop at same price level.
- **Bid/ask imbalance**: aggregate bid vs ask skew in ±10% band.
- **Potential spoofing**: large wall appearing and disappearing in a short window.

## Project structure

- `app/main.py` — FastAPI startup/shutdown, mounts static assets
- `app/ingestion/metascalp_client.py` — WS ingestion + reconstruction + persistence pipeline
- `app/ingestion/orderbook.py` — order book state machine
- `app/db/clickhouse.py` — ClickHouse schema + batched writes + queries
- `app/analytics/signals.py` — signal generation logic
- `app/api/routes.py` — REST endpoints + dashboard route
- `app/templates/index.html`, `app/static/app.js` — basic frontend

## Run

```bash
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Environment variables (`.env`, prefix `OB_`):

- `OB_METASCALP_WS_URL=ws://127.0.0.1:8765`
- `OB_METASCALP_SYMBOL=BTCUSDT`
- `OB_CLICKHOUSE_HOST=127.0.0.1`
- `OB_CLICKHOUSE_PORT=8123`
- `OB_CLICKHOUSE_USER=default`
- `OB_CLICKHOUSE_PASSWORD=`
- `OB_CLICKHOUSE_DATABASE=orderbook`
- `OB_SNAPSHOT_INTERVAL_MS=1000`
- `OB_BATCH_SIZE=100`
