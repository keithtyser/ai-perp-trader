from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # openrouter
    openrouter_api_key: str
    openrouter_model: str = "deepseek/deepseek-v3.2-exp"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_referer: str = ""
    openrouter_title: str = "ai-perp-trader"

    # hyperliquid testnet
    hl_api_key: str = ""
    hl_api_secret: str = ""
    hl_account: str = ""
    hl_base_url: str = "https://api.hyperliquid-testnet.xyz"

    # database
    database_url: str

    # agent
    cycle_interval_seconds: int = 60  # 10 minutes
    min_notional: float = 5.0
    max_leverage: float = 100.0
    dry_run: bool = False

    # trading backend: hyperliquid or perpsim
    trading_backend: str = "perpsim"

    # perpsim config
    sim_im: float = 0.05
    sim_mm: float = 0.03
    sim_max_leverage: float = 100.0
    sim_slippage_bps: float = 1.0
    sim_fee_bps: float = 2.0
    sim_liq_penalty_bps: float = 5.0
    sim_funding_mode: str = "A"  # A=0%, B=heuristic, C=external
    sim_symbols: str = "BTC-USD,ETH-USD"
    sim_tick_size: float = 0.5  # default tick size

    # per-symbol tick sizes (override default)
    @property
    def tick_sizes(self) -> dict[str, float]:
        return {
            "BTC-USD": 0.5,      # $113,000 -> 113000.0, 113000.5, 113001.0
            "ETH-USD": 0.01,     # $4,060 -> 4060.00, 4060.01, 4060.02
            "SOL-USD": 0.01,     # $199 -> 199.00, 199.01, 199.02
            "DOGE-USD": 0.00001, # $0.20 -> 0.20240, 0.20241, 0.20242
            "XRP-USD": 0.0001,   # $2.62 -> 2.6234, 2.6235, 2.6236
            "BTC-PERP": 0.5,
            "ETH-PERP": 0.01,
        }

    # data feed
    data_feed: str = "coinbase"
    coinbase_ws_url: str = "wss://ws-feed.exchange.coinbase.com"

    # agent version (semantic versioning)
    agent_version: str = "v2.0.0"  # Update this before each deployment
    version_description: str = "YOLO Degen Mode"  # Describe what changed

    class Config:
        env_file = ".env"


settings = Settings()
