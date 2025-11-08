# AI Perp Trader

An autonomous LLM trading agent with **paper trading** (PerpSim) and optional Hyperliquid testnet support, powered by **DeepSeek V3.2** via **OpenRouter**.

**[Watch it trade live →](https://trade.keithtyser.com/)**

## Features

### Core Trading
- **Paper Trading (PerpSim)**: Realistic perpetual futures simulator with leverage up to 100x (default 5x)
- **Live Spot Data**: Coinbase WebSocket feed for BTC-USD, ETH-USD, SOL-USD, DOGE-USD, XRP-USD
- **Margin & Liquidation**: Enforces initial/maintenance margin, auto-liquidates positions
- **Funding Simulation**: Configurable funding rate models (0%, heuristic, or external)
- **Autonomous LLM Planning**: DeepSeek V3.2 makes all trading decisions via structured JSON
- **Optional Hyperliquid Testnet**: Switch to live testnet mode with `TRADING_BACKEND=hyperliquid`

### Intelligence & Analysis
- **Market Regime Detection**: Automatically classifies markets as trending, ranging, or volatile
- **Technical Indicators**: RSI(7), MACD, EMA20, realized volatility, 6-hour candle context
- **Trade Reasoning**: Stores and displays entry/exit justifications for every trade
- **Recent Trade History**: Agent sees its last 10 completed trades with P&L and reasons

### Version Management
- **Agent Version Tracking**: Tag each deployment with semantic versioning (v1.0.0, v1.1.0, etc.)
- **Performance Isolation**: Each version tracks its own trades, equity curve, and metrics
- **Leaderboard**: Compare Sharpe ratio, win rate, and returns across different versions
- **A/B Testing**: Run multiple versions and see which strategy performs best

### Dashboard & API
- **Read-Only Dashboard**: Next.js app showing equity curve, positions, trades, performance metrics
- **FastAPI Backend**: Stable read-only endpoints for all data with version filtering
- **PostgreSQL**: Persistent storage for trades, positions, equity snapshots, and version metadata
- **Docker Compose**: One command to run everything locally

## Architecture

```
┌─────────────┐
│   Next.js   │ ← User views dashboard
│  Dashboard  │
└──────┬──────┘
       │ HTTP
       ↓
┌─────────────┐
│   FastAPI   │ ← Read-only API
│     API     │
└──────┬──────┘
       │ SQL
       ↓
┌─────────────┐     ┌──────────────┐
│  Postgres   │ ←── │    Worker    │ ← Agent loop
│  /Supabase  │     │ (Python 3.11)│
└─────────────┘     └──────┬───────┘
                           │
                    ┌──────┴───────────┐
                    │                  │
                    ↓                  ↓
            ┌───────────┐   ┌──────────────────┐
            │ OpenRouter│   │ Trading Backend: │
            │DeepSeek V3│   │  • PerpSim       │
            └───────────┘   │  • Hyperliquid   │
                            └──────────────────┘
```

## Quickstart (Paper Trading Mode - Recommended)

### Prerequisites

- Docker and Docker Compose
- OpenRouter API key (sign up at https://openrouter.ai)

### Steps

1. **Clone and navigate**
   ```bash
   git clone https://github.com/keithtyser/ai-perp-trader.git
   cd ai-perp-trader
   ```

2. **Set environment variables**
   ```bash
   cd infra
   cp .env.example .env
   # Edit .env with your OpenRouter API key:
   # OPENROUTER_API_KEY=your_key_here
   # TRADING_BACKEND=perpsim (default - paper trading)
   ```

3. **Start everything**
   ```bash
   docker-compose up --build
   ```

4. **View the dashboard**
   - Open http://localhost:3000
   - API docs at http://localhost:8000/docs
   - Database at localhost:5432 (user: agent, password: agent_password)

5. **Watch the logs**
   ```bash
   docker-compose logs -f worker
   ```

The agent will execute its first cycle within 1 minute (configurable). Check the dashboard to see equity snapshots, positions, trades, fees, funding, and model chat notes.

### Switching to Live Hyperliquid Testnet (Optional)

**Warning**: Only use testnet mode if you understand the regulatory implications.

1. Create a Hyperliquid testnet agent wallet at https://hyperliquid.xyz
2. Update `.env`:
   ```
   TRADING_BACKEND=hyperliquid
   HL_API_KEY=your_key
   HL_API_SECRET=your_secret
   HL_ACCOUNT=your_wallet_address
   ```
3. Restart: `docker-compose restart worker`

## Repository Structure

```
/apps
  /worker         # Python agent (executor, validator, reconciler)
  /api            # FastAPI read-only service
  /web            # Next.js dashboard
/infra            # Docker Compose, Dockerfiles, deploy guides
/db               # schema.sql, seed.sql
/docs             # ops guide, security notes, FAQ
/tests            # smoke tests and unit tests
README.md
Makefile
```

## Configuration

All agent behavior is controlled via environment variables:

### Worker
- `OPENROUTER_API_KEY` - OpenRouter API key
- `OPENROUTER_MODEL` - Model name (default: deepseek/deepseek-v3.2-exp)
- `TRADING_BACKEND` - Backend to use: `perpsim` (default) or `hyperliquid`
- `HL_API_KEY`, `HL_API_SECRET`, `HL_ACCOUNT` - Hyperliquid testnet credentials (only needed if TRADING_BACKEND=hyperliquid)
- `HL_BASE_URL` - Testnet URL (default: https://api.hyperliquid-testnet.xyz)
- `CYCLE_INTERVAL_SECONDS` - Decision cycle frequency (default: 60 = 1 minute)
- `MIN_NOTIONAL` - Minimum order size in USD (default: 5.0)
- `MAX_LEVERAGE` - Maximum allowed leverage (default: 5.0, max: 100.0 for PerpSim)
- `DRY_RUN` - If true, validate but don't execute trades (default: false)
- `SIM_SYMBOLS` - Comma-separated list of symbols for PerpSim (default: BTC-USD,ETH-USD,SOL-USD,DOGE-USD,XRP-USD)

### API
- `DATABASE_URL` - PostgreSQL connection string
- `CORS_ORIGINS` - Comma-separated allowed origins for CORS

### Web
- `NEXT_PUBLIC_API_BASE_URL` - URL of the FastAPI service

## How It Works

### 1. Observation Phase
Every cycle (default 1 minute), the worker builds a comprehensive observation containing:

**Market Data** (per symbol):
- Current price, spread, 24h volume
- Technical indicators: RSI(7), MACD, EMA20
- 1-minute OHLCV candles (last 60 minutes)
- 6-hour context candles (last 60 candles = ~15 days)
- Realized volatility, funding rate

**Market Regime Analysis**:
- Classification: Trending (bullish/bearish), Ranging, or Volatile
- Volatility level and direction strength
- Recommendations for the current regime

**Account State**:
- Equity, cash, positions with unrealized P/L
- Current leverage, margin usage
- Exit plans for each position (stop loss, take profit targets)

**Performance Context**:
- Recent 10 completed trades with entry/exit prices, P&L, hold time, and reasoning
- Win rate, Sharpe ratio, max drawdown (for current version only)
- Total trades, profit factor, average win/loss

**Limits & Constraints**:
- Min notional, tick size, max leverage per symbol

### 2. LLM Planning Phase
The observation is sent to **DeepSeek V3.2 via OpenRouter** with a system prompt. The LLM analyzes:
- Market conditions and regime
- Current positions and their performance
- Recent trade history and what worked/didn't work
- Risk management based on current equity

The LLM returns structured JSON with:
- `positions`: dict of coin -> PositionDecision
  - `signal`: buy/sell/hold/close
  - `quantity`: position size
  - `leverage`: 1-100x (default max 5x)
  - `exit_plan`: stop loss and take profit levels
  - `justification`: reasoning for this decision (max 500 chars)
- `notes_for_audience`: human-readable summary (max 1000 chars)

### 3. Execution Phase
The position manager translates decisions into market orders:
- Stores justifications and exit plans **before** execution
- Calculates target position sizes based on leverage and margin
- Places market orders with proper position sizing
- Tags trades with `entry_reason` (for new positions) or `exit_reason` (for closes)
- Logs detailed errors if insufficient margin or validation fails

### 4. Backend Execution
Orders are executed via the selected trading backend:
- **PerpSim** (default): Simulated fills with realistic slippage (1 bps) and fees (2 bps)
- **Hyperliquid**: Real testnet orders via signed REST API calls

### 5. Reconciliation Phase
After execution settles:
- Fetches updated account state from adapter
- Updates positions table with new quantities and P&L
- Inserts equity snapshot tagged with current `version_id`
- Records model chat note in database
- Updates version performance metrics (every 10 cycles)

### 6. Version Tracking
Each deployment is tagged with:
- `version_tag`: Semantic version (e.g., v1.0.6)
- `description`: What changed in this version
- `config`: Snapshot of model, leverage, symbols, etc.

All trades, equity snapshots, and performance metrics are filtered by version_id, so each version has isolated statistics.

### 7. Repeat
The loop sleeps for `CYCLE_INTERVAL_SECONDS` and starts again.

## Costs

- **OpenRouter**: ~$0.001–0.01 per cycle depending on model and context size (DeepSeek V3.2 is very cost-effective)
- **PerpSim**: Free (paper trading simulator)
- **Hyperliquid Testnet**: Free (testnet has no real fees)

## Version Management

The agent uses semantic versioning to track different deployments and strategies:

### Deploying a New Version

1. **Update version in config** (`apps/worker/config.py`):
   ```python
   agent_version: str = "v1.0.7"
   version_description: str = "Increased leverage to 10x and added SOL"
   ```

2. **Rebuild and restart**:
   ```bash
   docker compose up -d --build worker
   ```

3. **View performance**:
   - Each version gets its own equity curve, trade history, and performance metrics
   - The leaderboard at `/leaderboard` shows all versions ranked by Sharpe ratio
   - The dashboard filters to show only the currently active version

### Benefits

- **Isolated Testing**: Each version's performance is tracked separately
- **A/B Comparison**: Deploy v1.1.0 with higher leverage, see if it beats v1.0.0
- **Rollback Safety**: Can compare new strategy against historical baseline
- **Clear Attribution**: Know exactly which prompt/model/config produced which results

## Customization

### Add More Markets
Edit the `SIM_SYMBOLS` environment variable in `docker-compose.yml` or `.env`:
```bash
SIM_SYMBOLS=BTC-USD,ETH-USD,SOL-USD,DOGE-USD,XRP-USD,AVAX-USD
```

Make sure to add tick sizes in `apps/worker/config.py`:
```python
def tick_sizes(self) -> dict[str, float]:
    return {
        "BTC-USD": 0.5,
        "ETH-USD": 0.01,
        "AVAX-USD": 0.001,  # Add new symbol
        # ...
    }
```

### Adjust Cycle Frequency
Set `CYCLE_INTERVAL_SECONDS` in `.env` (e.g., 300 for 5 minutes, 3600 for 1 hour).

### Change LLM Model
Set `OPENROUTER_MODEL` in `.env` to any model available on OpenRouter:
```bash
# Cost-effective options:
OPENROUTER_MODEL=deepseek/deepseek-v3.2-exp
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
OPENROUTER_MODEL=google/gemini-2.5-pro

# High-performance options:
OPENROUTER_MODEL=openai/gpt-5
OPENROUTER_MODEL=x-ai/grok-4
```

For best results, use models with strong JSON mode and reasoning capabilities.

### Modify the System Prompt
Edit `apps/worker/system_prompt.py` to change trading strategy, risk management rules, or decision-making guidelines.

### Add Custom Indicators
Add indicator calculations in `apps/worker/main.py` in the `build_observation()` method. Include results in the observation JSON sent to the LLM.

Example:
```python
# Calculate custom indicator
bb_upper, bb_lower = calculate_bollinger_bands(candles)
market.bollinger_bands = {"upper": bb_upper, "lower": bb_lower}
```

The LLM will see this in the observation and can use it for decisions.

### Tune Validation Rules
Edit `apps/worker/validator.py` to add custom constraints:
- Maximum position size per symbol
- Symbol whitelisting/blacklisting
- Maximum total exposure
- Time-based trading restrictions

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## Acknowledgments

- [OpenRouter](https://openrouter.ai) for unified LLM API access
- [DeepSeek](https://www.deepseek.com/) for the DeepSeek V3.2 model
- [Hyperliquid](https://hyperliquid.xyz) for providing an optional live trading backend
- [Coinbase](https://www.coinbase.com/) for real-time market data via WebSocket
- Inspired by autonomous agent research and quantitative trading systems
