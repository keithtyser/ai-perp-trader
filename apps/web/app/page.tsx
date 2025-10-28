'use client';

import useSWR from 'swr';
import { api } from '@/lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceDot, Label } from 'recharts';

// Coin configuration for the chart
const COINS = [
  { symbol: 'BTC', name: 'BTC', color: '#F7931A', icon: '₿' },
  { symbol: 'ETH', name: 'ETH', color: '#627EEA', icon: '♦' },
  { symbol: 'SOL', name: 'SOL', color: '#14F195', icon: '◎' },
  { symbol: 'DOGE', name: 'DOGE', color: '#C3A634', icon: 'Ð' },
  { symbol: 'XRP', name: 'XRP', color: '#23292F', icon: '✕' },
];

export default function OverviewPage() {
  const { data: equity } = useSWR('equity-curve', api.getEquityCurve, {
    refreshInterval: 30000,
  });
  const { data: pl } = useSWR('pl', api.getPL, { refreshInterval: 30000 });
  const { data: prices } = useSWR('market-prices', api.getMarketPrices, {
    refreshInterval: 5000, // Update prices every 5 seconds
  });
  const { data: perfStats } = useSWR('performance-stats', api.getPerformanceStats, {
    refreshInterval: 30000,
  });

  const chartData = equity?.map((point) => {
    const date = new Date(point.ts);
    const month = date.toLocaleString('en', { month: 'short' });
    const day = date.getDate();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return {
      time: `${month} ${day} ${hours}:${minutes}`,
      equity: point.equity,
      timestamp: point.ts,
    };
  });

  // Calculate performance stats
  const startEquity = equity?.[0]?.equity || 10000;
  const currentEquity = pl?.current_equity || startEquity;
  const returnPct = ((currentEquity - startEquity) / startEquity) * 100;
  const returnColor = returnPct >= 0 ? 'text-green-500' : 'text-red-500';

  // Calculate highest and lowest return percentages from equity curve
  let highestReturnPct: number | null = null;
  let lowestReturnPct: number | null = null;
  if (equity && equity.length > 1) {
    const maxEquity = Math.max(...equity.map(p => p.equity));
    const minEquity = Math.min(...equity.map(p => p.equity));
    highestReturnPct = ((maxEquity - startEquity) / startEquity) * 100;
    lowestReturnPct = ((minEquity - startEquity) / startEquity) * 100;
  }

  // Helper to get price for a coin
  const getPrice = (symbol: string) => {
    if (!prices) return '--';
    const fullSymbol = `${symbol}-USD`;
    return prices[fullSymbol]?.price.toFixed(2) || '--';
  };

  return (
    <div className="space-y-6">
      {/* Header with coin prices */}
      <div className="bg-gray-900 text-white rounded-lg p-4">
        <div className="flex flex-wrap gap-6 items-center justify-between">
          {COINS.map((coin) => (
            <div key={coin.symbol} className="flex items-center gap-2">
              <span className="text-2xl">{coin.icon}</span>
              <div>
                <div className="text-xs text-gray-400">{coin.name}</div>
                <div className="text-lg font-semibold">${getPrice(coin.symbol)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">TOTAL ACCOUNT VALUE</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">
            ${currentEquity.toFixed(2)}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">HIGHEST</div>
          <div className="text-lg font-semibold text-green-500">
            {highestReturnPct === null ? '--' : highestReturnPct > 0 ? `+${highestReturnPct.toFixed(2)}%` : `${highestReturnPct.toFixed(2)}%`}
          </div>
          <div className="text-xs text-gray-400">Keith's Crypto Agent</div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">LOWEST</div>
          <div className="text-lg font-semibold text-red-500">
            {lowestReturnPct === null ? '--' : lowestReturnPct < 0 ? `${lowestReturnPct.toFixed(2)}%` : `+${lowestReturnPct.toFixed(2)}%`}
          </div>
          <div className="text-xs text-gray-400">Keith's Crypto Agent</div>
        </div>
      </div>

      {/* Trading Performance Statistics */}
      {perfStats && perfStats.total_trades > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 border border-gray-200 dark:border-gray-700">
          <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
            Trading Performance Statistics
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {/* Win Rate */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">WIN RATE</div>
              <div className={`text-2xl font-bold ${perfStats.win_rate >= 50 ? 'text-green-500' : 'text-yellow-500'}`}>
                {perfStats.win_rate.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {perfStats.winning_trades}W / {perfStats.losing_trades}L
              </div>
            </div>

            {/* Profit Factor */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">PROFIT FACTOR</div>
              <div className={`text-2xl font-bold ${perfStats.profit_factor >= 1.5 ? 'text-green-500' : perfStats.profit_factor >= 1.0 ? 'text-yellow-500' : 'text-red-500'}`}>
                {perfStats.profit_factor.toFixed(2)}x
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {perfStats.profit_factor >= 2.0 ? 'Excellent' : perfStats.profit_factor >= 1.5 ? 'Good' : perfStats.profit_factor >= 1.0 ? 'Profitable' : 'Losing'}
              </div>
            </div>

            {/* Average Win */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">AVG WIN</div>
              <div className="text-2xl font-bold text-green-500">
                ${perfStats.avg_win.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Max: ${perfStats.largest_win.toFixed(2)}
              </div>
            </div>

            {/* Average Loss */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">AVG LOSS</div>
              <div className="text-2xl font-bold text-red-500">
                ${perfStats.avg_loss.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Max: ${perfStats.largest_loss.toFixed(2)}
              </div>
            </div>

            {/* Total Trades */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">TOTAL TRADES</div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {perfStats.total_trades}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Completed
              </div>
            </div>

            {/* Avg Hold Time */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">AVG HOLD TIME</div>
              <div className={`text-2xl font-bold ${perfStats.avg_hold_time_minutes >= 10 ? 'text-green-500' : perfStats.avg_hold_time_minutes >= 5 ? 'text-yellow-500' : 'text-red-500'}`}>
                {perfStats.avg_hold_time_minutes.toFixed(1)}m
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {perfStats.avg_hold_time_minutes < 5 ? 'Churning' : perfStats.avg_hold_time_minutes < 10 ? 'Short-term' : 'Good'}
              </div>
            </div>

            {/* Sharpe Ratio */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">SHARPE (30D)</div>
              <div className={`text-2xl font-bold ${perfStats.sharpe_30d >= 2.0 ? 'text-green-500' : perfStats.sharpe_30d >= 1.0 ? 'text-yellow-500' : 'text-gray-500'}`}>
                {perfStats.sharpe_30d.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Risk-adjusted
              </div>
            </div>

            {/* Max Drawdown */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">MAX DRAWDOWN</div>
              <div className="text-2xl font-bold text-red-500">
                {perfStats.max_dd.toFixed(2)}%
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Peak to trough
              </div>
            </div>

            {/* Total Volume */}
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">TOTAL VOLUME</div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                ${perfStats.total_volume >= 1000 ? (perfStats.total_volume / 1000).toFixed(1) + 'k' : perfStats.total_volume.toFixed(0)}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Traded
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Chart */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 border border-gray-200 dark:border-gray-700">
        <div className="mb-4">
          <h3 className="text-xl font-bold text-gray-900 dark:text-white">
            Total Account Value
          </h3>
        </div>
        {chartData && chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={500}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
              <XAxis
                dataKey="time"
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF', fontSize: 11 }}
                interval="preserveStartEnd"
                minTickGap={50}
              />
              <YAxis
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF', fontSize: 12 }}
                domain={['auto', 'auto']}
                tickFormatter={(value) => `$${value.toLocaleString()}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: '8px',
                  color: '#F3F4F6',
                }}
                formatter={(value: number) => [`$${value.toFixed(2)}`, 'Account Value']}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="equity"
                name="Keith's Crypto Agent"
                stroke="#14F195"
                strokeWidth={3}
                dot={false}
                activeDot={{
                  r: 8,
                  fill: '#14F195',
                  stroke: '#fff',
                  strokeWidth: 2,
                }}
              />
              {/* Current value indicator on last point */}
              {chartData.length > 0 && (
                <ReferenceDot
                  x={chartData[chartData.length - 1].time}
                  y={chartData[chartData.length - 1].equity}
                  r={6}
                  fill="#6366f1"
                  stroke="#fff"
                  strokeWidth={3}
                  label={{
                    value: `$${currentEquity.toFixed(2)}`,
                    position: 'top',
                    fill: '#fff',
                    fontSize: 14,
                    fontWeight: 'bold',
                    style: {
                      background: '#6366f1',
                      padding: '4px 12px',
                      borderRadius: '6px',
                    }
                  }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-96 flex items-center justify-center text-gray-500">
            No data yet - waiting for agent to start trading...
          </div>
        )}
      </div>
    </div>
  );
}

