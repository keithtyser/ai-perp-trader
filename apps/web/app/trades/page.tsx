'use client';

import useSWR from 'swr';
import { api } from '@/lib/api';
import { useState } from 'react';

const COIN_INFO: Record<string, { icon: string; color: string }> = {
  'BTC-USD': { icon: '₿', color: '#F7931A' },
  'ETH-USD': { icon: '♦', color: '#627EEA' },
  'SOL-USD': { icon: '◎', color: '#14F195' },
  'DOGE-USD': { icon: 'Ð', color: '#C3A634' },
  'XRP-USD': { icon: '✕', color: '#23292F' },
};

export default function TradesPage() {
  const [limit] = useState(50);

  const { data: trades, error } = useSWR(
    ['completed-trades', limit],
    () => api.getCompletedTrades(limit),
    { refreshInterval: 30000 }
  );

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            COMPLETED TRADES
          </h2>
        </div>
        <div>
          <select className="bg-gray-900 text-white px-4 py-2 rounded border border-gray-700">
            <option>ALL MODELS</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-4 rounded">
          Failed to load trades
        </div>
      )}

      {!trades && !error && (
        <div className="text-gray-500">Loading trades...</div>
      )}

      {trades && trades.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center text-gray-500">
          No trades yet
        </div>
      )}

      {trades && trades.length > 0 && (
        <div className="space-y-4">
          {trades.map((trade, index) => {
            const coinInfo = COIN_INFO[trade.symbol] || { icon: '●', color: '#666' };

            return (
              <div
                key={index}
                className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center text-white">
                      ◎
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">
                        Keith's Crypto Agent
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(trade.exit_time).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-2xl font-bold ${trade.net_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      NET P&L: ${trade.net_pnl.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 md:grid-cols-6 gap-4">
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">DIRECTION</div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-1 rounded text-sm font-bold ${
                          trade.direction === 'long'
                            ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                            : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                        }`}
                      >
                        {trade.direction.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">COIN</div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl" style={{ color: coinInfo.color }}>
                        {coinInfo.icon}
                      </span>
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {trade.symbol.replace('-USD', '')}
                      </span>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">ENTRY PRICE</div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">
                      ${trade.entry_price.toFixed(2)}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">EXIT PRICE</div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">
                      ${trade.exit_price.toFixed(2)}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">QUANTITY</div>
                    <div className="font-medium text-gray-900 dark:text-white">
                      {trade.qty.toFixed(4)}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">HOLDING TIME</div>
                    <div className="font-medium text-gray-900 dark:text-white">
                      {trade.holding_time_display}
                    </div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Entry Notional: </span>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      ${trade.entry_notional.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Exit Notional: </span>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      ${trade.exit_notional.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Fees: </span>
                    <span className="font-semibold text-red-500">
                      -${trade.fees.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
