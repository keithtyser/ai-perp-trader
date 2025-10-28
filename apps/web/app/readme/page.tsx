export default function ReadmePage() {
  return (
    <div className="prose prose-gray dark:prose-invert max-w-none">
      <h1>Keith's Crypto Agent Dashboard</h1>

      <p>
        This is a fun project to see how good of a trading agent I can make! It uses
        Deepseek v3.2 via OpenRouter to make trading decisions. All trading is paper trading
        only - no real money involved. Inspired by{" "}
        <a
          href="https://nof1.ai/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400"
        >
          Alpha Arena
        </a>.
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
          Deepseek v3.2, validates actions, and executes trades
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
