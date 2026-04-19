from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MetaScalp Order Book Analytics"
    metascalp_ws_url: str = "ws://127.0.0.1:8765"
    metascalp_symbol: str = "BTCUSDT"

    clickhouse_host: str = "127.0.0.1"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "orderbook"

    snapshot_interval_ms: int = 1000
    batch_size: int = 100

    model_config = SettingsConfigDict(env_file=".env", env_prefix="OB_")


settings = Settings()
