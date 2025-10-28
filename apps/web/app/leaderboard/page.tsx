'use client';

import useSWR from 'swr';
import { api } from '@/lib/api';
import { useState } from 'react';

export default function LeaderboardPage() {
  const [minHours, setMinHours] = useState(0);

  const { data: versions, error } = useSWR(
    ['leaderboard', minHours],
    () => api.getLeaderboard(minHours),
    { refreshInterval: 30000 }
  );

  const { data: currentVersion } = useSWR(
    'current-version',
    () => api.getCurrentVersion(),
    { refreshInterval: 30000 }
  );

  const formatDuration = (days: number) => {
    if (days < 1) {
      const hours = days * 24;
      if (hours < 1) {
        return `${Math.round(hours * 60)}m`;
      }
      return `${hours.toFixed(1)}h`;
    }
    return `${days.toFixed(1)}d`;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            VERSION LEADERBOARD
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Track performance across different agent versions
          </p>
        </div>
      </div>

      {currentVersion && (
        <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
            <div>
              <div className="font-semibold text-emerald-900 dark:text-emerald-100">
                Currently Active: {currentVersion.version_tag}
              </div>
              <div className="text-sm text-emerald-700 dark:text-emerald-300">
                {currentVersion.description}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Minimum Duration:
          </label>
          <select
            value={minHours}
            onChange={(e) => setMinHours(Number(e.target.value))}
            className="px-3 py-1.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded text-sm text-gray-900 dark:text-white"
          >
            <option value={0}>All versions</option>
            <option value={1}>1+ hours</option>
            <option value={6}>6+ hours</option>
            <option value={24}>24+ hours</option>
            <option value={72}>3+ days</option>
            <option value={168}>7+ days</option>
          </select>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Sorted by Sharpe Ratio (risk-adjusted performance)
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-4 rounded">
          Failed to load leaderboard
        </div>
      )}

      {!versions && !error && (
        <div className="text-gray-500">Loading leaderboard...</div>
      )}

      {versions && versions.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center text-gray-500">
          No versions found with selected criteria
        </div>
      )}

      {versions && versions.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Rank
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Version
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Total Return
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Daily Return
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Sharpe Ratio
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Max DD
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Trades
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Win Rate
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Profit Factor
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {versions.map((version, index) => (
                  <tr
                    key={version.version_tag}
                    className={
                      version.is_active
                        ? 'bg-emerald-50 dark:bg-emerald-900/10'
                        : index % 2 === 0
                        ? 'bg-white dark:bg-gray-800'
                        : 'bg-gray-50 dark:bg-gray-900/50'
                    }
                  >
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          #{index + 1}
                        </span>
                        {index === 0 && (
                          <span className="text-yellow-500" title="Best Performance">
                            🏆
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {version.is_active && (
                          <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                        )}
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {version.version_tag}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate">
                            {version.description}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm text-gray-900 dark:text-white">
                        {formatDuration(version.duration_days)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {version.total_cycles} cycles
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <span
                        className={`text-sm font-medium ${
                          version.total_return_pct >= 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-red-600 dark:text-red-400'
                        }`}
                      >
                        {version.total_return_pct >= 0 ? '+' : ''}
                        {version.total_return_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <span
                        className={`text-sm ${
                          version.daily_return_pct >= 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-red-600 dark:text-red-400'
                        }`}
                      >
                        {version.daily_return_pct >= 0 ? '+' : ''}
                        {version.daily_return_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <span
                        className={`text-sm font-medium ${
                          version.sharpe_ratio >= 2
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : version.sharpe_ratio >= 1
                            ? 'text-blue-600 dark:text-blue-400'
                            : 'text-gray-600 dark:text-gray-400'
                        }`}
                      >
                        {version.sharpe_ratio.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <span className="text-sm text-red-600 dark:text-red-400">
                        {version.max_drawdown_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <div className="text-sm text-gray-900 dark:text-white">
                        {version.total_trades}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {version.trades_per_day.toFixed(1)}/day
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <span className="text-sm text-gray-900 dark:text-white">
                        {version.win_rate.toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <span
                        className={`text-sm ${
                          version.profit_factor >= 2
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : version.profit_factor >= 1
                            ? 'text-blue-600 dark:text-blue-400'
                            : 'text-gray-600 dark:text-gray-400'
                        }`}
                      >
                        {version.profit_factor.toFixed(2)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
          Metric Definitions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-gray-600 dark:text-gray-400">
          <div>
            <span className="font-medium text-gray-900 dark:text-white">Total Return:</span> Overall profit/loss percentage
          </div>
          <div>
            <span className="font-medium text-gray-900 dark:text-white">Daily Return:</span> Average return per day (for fair comparison)
          </div>
          <div>
            <span className="font-medium text-gray-900 dark:text-white">Sharpe Ratio:</span> Risk-adjusted performance (&gt;2.0 = excellent, 1-2 = good)
          </div>
          <div>
            <span className="font-medium text-gray-900 dark:text-white">Max DD:</span> Worst peak-to-trough decline
          </div>
          <div>
            <span className="font-medium text-gray-900 dark:text-white">Win Rate:</span> Percentage of profitable trades
          </div>
          <div>
            <span className="font-medium text-gray-900 dark:text-white">Profit Factor:</span> Avg win / Avg loss (&gt;2.0 = excellent)
          </div>
        </div>
      </div>
    </div>
  );
}
