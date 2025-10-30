# AI Perp Trader

An autonomous LLM trading agent with **paper trading** (PerpSim) and optional Hyperliquid testnet support, powered by **Qwen3-Max** via **OpenRouter**.

**[Watch it trade live →](https://trade.keithtyser.com/)**

## Features

- **Paper Trading (PerpSim)**: Realistic perpetual futures simulator with leverage up to 20x
- **Live Spot Data**: Coinbase WebSocket feed for BTC-USD, ETH-USD, SOL-USD, DOGE-USD, XRP-USD
- **Margin & Liquidation**: Enforces initial/maintenance margin, auto-liquidates positions
- **Funding Simulation**: Configurable funding rate models (0%, heuristic, or external)
- **Autonomous LLM Planning**: Qwen3-Max makes all trading decisions via structured JSON
- **Optional Hyperliquid Testnet**: Switch to live testnet mode with `TRADING_BACKEND=hyperliquid`
- **Read-Only Dashboard**: Next.js app showing equity curve, positions, trades, fees, and funding
- **FastAPI Backend**: Stable read-only endpoints for all data
- **PostgreSQL**: Persistent storage for trades, positions, and equity snapshots
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
            │ Qwen3-Max │   │  • PerpSim       │
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
- `OPENROUTER_MODEL` - Model name (default: qwen/qwen3-max)
- `TRADING_BACKEND` - Backend to use: `perpsim` (default) or `hyperliquid`
- `HL_API_KEY`, `HL_API_SECRET`, `HL_ACCOUNT` - Hyperliquid testnet credentials (only needed if TRADING_BACKEND=hyperliquid)
- `HL_BASE_URL` - Testnet URL (default: https://api.hyperliquid-testnet.xyz)
- `CYCLE_INTERVAL_SECONDS` - Decision cycle frequency (default: 60 = 1 minute)
- `MIN_NOTIONAL` - Minimum order size in USD (default: 5.0)
- `MAX_LEVERAGE` - Maximum allowed leverage (default: 20.0)
- `DRY_RUN` - If true, validate but don't execute trades (default: false)
- `SIM_SYMBOLS` - Comma-separated list of symbols for PerpSim (default: BTC-USD,ETH-USD)

### API
- `DATABASE_URL` - PostgreSQL connection string
- `CORS_ORIGINS` - Comma-separated allowed origins for CORS

### Web
- `NEXT_PUBLIC_API_BASE_URL` - URL of the FastAPI service

## How It Works

### 1. Observation Phase
Every cycle (default 1 minute), the worker builds an observation JSON containing:
- Market data: mid price, spread, OHLCV candles, realized vol, funding rate
- Account data: equity, cash, positions, unrealized P/L, fees paid
- Limits: min notional, tick size, max leverage
- Scoreboard: all-time P/L, Sharpe ratio, max drawdown
- Last error: validation message from previous cycle (if any)

### 2. LLM Planning Phase
The worker sends the observation to **Qwen3-Max via OpenRouter** with a strict system prompt. The LLM must return valid JSON with:
- `decisions`: dict of symbol -> PositionDecision (signal: buy/sell/hold/close, leverage: 1-20x)
- `notes_for_audience`: short text note (max 220 chars) explaining the decision

### 3. Execution Phase
The position manager translates high-level decisions into market orders:
- Calculates target position sizes based on requested leverage and available margin
- Places market orders to reach target positions (IOC time-in-force)
- Handles insufficient margin by logging detailed error messages
- All errors are visible to the agent in the next cycle's observation

### 4. Backend Execution
Orders are executed via the selected trading backend:
- **PerpSim** (default): Simulated fills with configurable slippage and fees
- **Hyperliquid**: Real testnet orders via signed REST API calls

### 5. Reconciliation Phase
After a brief delay (for fills to settle), the reconciler:
- Fetches updated account state
- Updates positions table
- Inserts equity snapshot (timestamped)
- Writes model chat note to database

### 6. Repeat
The loop sleeps for `CYCLE_INTERVAL_SECONDS` and starts again.

## Costs

- **OpenRouter**: ~$0.001–0.01 per cycle depending on model and context size (Qwen3-Max is cost-effective)
- **PerpSim**: Free (paper trading simulator)
- **Hyperliquid Testnet**: Free (testnet has no real fees)

## Customization

### Add More Markets
Edit `apps/worker/main.py` in `build_observation()` to add symbols to the loop:
```python
for symbol in ["BTC-PERP", "ETH-PERP", "SOL-PERP"]:
    # fetch market data...
```

### Adjust Cycle Frequency
Set `CYCLE_INTERVAL_SECONDS` to desired seconds (e.g., 300 for 5 minutes).

### Change LLM Model
Set `OPENROUTER_MODEL` to any model available on OpenRouter. For best results, use a model that supports JSON mode.

### Tune Validation Rules
Edit `apps/worker/validator.py` to add custom constraints (e.g., max position size, symbol whitelist).

**Q: How do I add custom indicators?**
A: Add indicator functions to `apps/worker/main.py` in `build_observation()`. Include the results in the observation JSON sent to the LLM.

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## Acknowledgments

- [OpenRouter](https://openrouter.ai) for unified LLM API access
- [Qwen](https://www.alibabacloud.com/en/solutions/generative-ai/qwen) for the Qwen3-Max model
- [Hyperliquid](https://hyperliquid.xyz) for providing an optional live trading backend
- Inspired by autonomous agent research and the nof1 dashboard
