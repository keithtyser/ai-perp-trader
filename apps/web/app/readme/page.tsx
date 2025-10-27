export default function ReadmePage() {
  return (
    <div className="prose prose-gray dark:prose-invert max-w-none">
      <h1>Keith's Crypto Agent Dashboard</h1>

      <p>
        This is a read-only dashboard for an autonomous trading agent. The agent
        uses paper trading (PerpSim) by default, with optional Hyperliquid testnet
        support. It uses Qwen3-Max via OpenRouter to make trading decisions.
      </p>

      <h2>Pages</h2>
      <ul>
        <li>
          <strong>Overview:</strong> Equity curve and summary statistics
        </li>
        <li>
          <strong>Positions:</strong> Current open positions
        </li>
        <li>
          <strong>Trades:</strong> All completed trades
        </li>
        <li>
          <strong>Model Chat:</strong> Decision notes from each cycle
        </li>
      </ul>

      <h2>Architecture</h2>
      <ul>
        <li>
          <strong>Worker:</strong> Python agent that observes markets, calls
          Qwen3-Max, validates actions, and executes trades
        </li>
        <li>
          <strong>API:</strong> FastAPI service with read-only endpoints
        </li>
        <li>
          <strong>Web:</strong> Next.js dashboard (this app)
        </li>
        <li>
          <strong>Database:</strong> PostgreSQL/Supabase for state persistence
        </li>
      </ul>

      <h2>Safety</h2>
      <p>
        By default, the agent runs in <strong>paper trading mode (PerpSim)</strong> with
        no real money at risk. Optionally, it can connect to Hyperliquid{" "}
        <strong>testnet</strong> using an agent wallet with no withdrawal permissions.
        All trades are validated against platform constraints before execution.
      </p>

      <h2>Links</h2>
      <ul>
        <li>
          <a
            href="https://github.com/keithtyser/ai-perp-trader"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400"
          >
            GitHub Repository
          </a>
        </li>
        <li>
          <a
            href="https://openrouter.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400"
          >
            OpenRouter
          </a>
        </li>
        <li>
          <a
            href="https://hyperliquid.xyz"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400"
          >
            Hyperliquid
          </a>
        </li>
      </ul>
    </div>
  );
}
