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
  'BNB-USD': { icon: '◆', color: '#F3BA2F' },
};

export default function PositionsPage() {
  const { data: positions, error } = useSWR('positions', api.getPositions, {
    refreshInterval: 10000,
  });
  const { data: pl } = useSWR('pl', api.getPL, { refreshInterval: 10000 });

  const [showExitPlan, setShowExitPlan] = useState<string | null>(null);

  const totalUnrealizedPnl = positions?.reduce((sum, pos) => sum + pos.unrealized_pl, 0) || 0;
  const availableCash = pl?.current_equity ? pl.current_equity - (pl?.current_equity - totalUnrealizedPnl) : 0;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            POSITIONS
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
          Failed to load positions
        </div>
      )}

      {!positions && !error && (
        <div className="text-gray-500">Loading positions...</div>
      )}

      {positions && positions.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center text-gray-500">
          No open positions
        </div>
      )}

      {positions && positions.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          {/* Model Header */}
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between bg-gray-50 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center text-white">
                <span className="text-xl">◎</span>
              </div>
              <div>
                <div className="font-bold text-lg text-gray-900 dark:text-white">KEITH'S CRYPTO AGENT</div>
                <div className="text-sm text-gray-500">
                  TOTAL UNREALIZED P&L:
                  <span className={`ml-2 font-bold ${totalUnrealizedPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ${totalUnrealizedPnl.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-500 dark:text-gray-400">AVAILABLE CASH</div>
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                ${availableCash.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Positions Table */}
          <table className="min-w-full">
            <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  SIDE
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  COIN
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  LEVERAGE
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  NOTIONAL
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  EXIT PLAN
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  UNREAL P&L
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {positions.map((pos) => {
                const coinInfo = COIN_INFO[pos.symbol] || { icon: '●', color: '#666' };
                const side = pos.qty > 0 ? 'LONG' : 'SHORT';
                const notional = Math.abs(pos.qty * pos.avg_entry);
                // Use actual leverage from API response
                const leverage = pos.leverage || 1;

                return (
                  <>
                    <tr key={pos.symbol}>
                      <td className="px-6 py-4">
                        <span
                          className={`px-3 py-1 rounded font-bold text-sm ${
                            side === 'LONG'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                              : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                          }`}
                        >
                          {side}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl" style={{ color: coinInfo.color }}>
                            {coinInfo.icon}
                          </span>
                          <span className="font-semibold text-gray-900 dark:text-white">
                            {pos.symbol.replace('-USD', '')}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="font-bold text-gray-900 dark:text-white">
                          {leverage}X
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right font-semibold text-gray-900 dark:text-white">
                        ${notional.toFixed(0)}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => setShowExitPlan(showExitPlan === pos.symbol ? null : pos.symbol)}
                          className="px-3 py-1 bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white rounded text-sm font-medium hover:bg-gray-300 dark:hover:bg-gray-600"
                        >
                          {showExitPlan === pos.symbol ? 'HIDE' : 'VIEW'}
                        </button>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className={`font-bold text-lg ${pos.unrealized_pl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {pos.unrealized_pl >= 0 ? '+' : ''}${pos.unrealized_pl.toFixed(2)}
                        </span>
                      </td>
                    </tr>
                    {showExitPlan === pos.symbol && pos.exit_plan && (
                      <tr key={`${pos.symbol}-exit-plan`}>
                        <td colSpan={6} className="px-6 py-4 bg-gray-50 dark:bg-gray-900">
                          <div className="space-y-2">
                            <div className="font-bold text-sm text-gray-700 dark:text-gray-300">Exit Plan:</div>
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Target: </span>
                                <span className="font-semibold text-gray-900 dark:text-white">
                                  ${pos.exit_plan.profit_target.toFixed(2)}
                                </span>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Stop: </span>
                                <span className="font-semibold text-gray-900 dark:text-white">
                                  ${pos.exit_plan.stop_loss.toFixed(2)}
                                </span>
                              </div>
                            </div>
                            <div className="text-sm">
                              <span className="text-gray-500 dark:text-gray-400">Invalid Condition: </span>
                              <span className="text-gray-900 dark:text-white">
                                {pos.exit_plan.invalidation_condition}
                              </span>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                    {showExitPlan === pos.symbol && !pos.exit_plan && (
                      <tr key={`${pos.symbol}-exit-plan`}>
                        <td colSpan={6} className="px-6 py-4 bg-gray-50 dark:bg-gray-900 text-center text-gray-500 dark:text-gray-400 text-sm">
                          No exit plan available
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
