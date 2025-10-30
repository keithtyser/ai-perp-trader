const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export interface EquityPoint {
  ts: string;
  equity: number;
  cash: number;
  unrealized_pl: number;
  realized: number;
  fees: number;
  funding: number;
}

export interface ExitPlan {
  profit_target: number;
  stop_loss: number;
  invalidation_condition: string;
}

export interface Position {
  symbol: string;
  qty: number;
  avg_entry: number;
  unrealized_pl: number;
  leverage: number;
  updated_at: string;
  exit_plan?: ExitPlan | null;
}

export interface Trade {
  id: number;
  ts: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  fee: number;
  client_id: string;
}

export interface CompletedTrade {
  symbol: string;
  direction: 'long' | 'short';
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  qty: number;
  entry_notional: number;
  exit_notional: number;
  holding_time_seconds: number;
  holding_time_display: string;
  gross_pnl: number;
  fees: number;
  net_pnl: number;
}

export interface PLSummary {
  pnl_all_time: number;
  fees_paid_total: number;
  max_drawdown: number;
  current_equity: number;
  unrealized_pl: number;
  available_cash: number;
}

export interface ChatMessage {
  id: number;
  ts: string;
  content: string;
  cycle_id: string;
  observation_prompt?: string;
  action_response?: any;
}

export interface Metrics {
  pnl_all_time: number;
  sharpe_30d: number;
  max_dd: number;
  fee_pct: number;
  funding_net: number;
  current_equity: number;
  sim_fees: number;
  sim_realized: number;
}

export interface MarketPrice {
  price: number;
  updated_at: string;
}

export interface MarketPrices {
  [symbol: string]: MarketPrice;
}

export interface PerformanceStats {
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  largest_win: number;
  largest_loss: number;
  avg_hold_time_minutes: number;
  total_volume: number;
  sharpe_30d: number;
  max_dd: number;
}

export interface VersionPerformance {
  version_tag: string;
  description: string;
  deployed_at: string | null;
  retired_at: string | null;
  is_active: boolean;
  duration_days: number;
  total_cycles: number;
  total_return_pct: number;
  daily_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
  trades_per_day: number;
  win_rate: number;
  profit_factor: number;
  avg_hold_time_minutes: number;
  realized_pnl: number;
  total_fees: number;
  pnl_per_day: number;
  starting_equity: number;
  ending_equity: number;
}

export interface CurrentVersion {
  version_tag: string;
  description: string;
  deployed_at: string;
  started_at: string;
}

async function fetchAPI<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getEquityCurve: () => fetchAPI<EquityPoint[]>('/equity-curve'),
  getPositions: () => fetchAPI<Position[]>('/positions'),
  getTrades: (limit = 100, offset = 0) =>
    fetchAPI<Trade[]>(`/trades?limit=${limit}&offset=${offset}`),
  getCompletedTrades: (limit = 50) =>
    fetchAPI<CompletedTrade[]>(`/completed-trades?limit=${limit}`),
  getPL: () => fetchAPI<PLSummary>('/pl'),
  getChat: (limit = 50, offset = 0) =>
    fetchAPI<ChatMessage[]>(`/chat?limit=${limit}&offset=${offset}`),
  getMetrics: () => fetchAPI<Metrics>('/metrics'),
  getHealth: () => fetchAPI<{status: string; timestamp: string}>('/health'),
  getMarketPrices: () => fetchAPI<MarketPrices>('/market-prices'),
  getPerformanceStats: () => fetchAPI<PerformanceStats>('/performance-stats'),
  getLeaderboard: (minHours = 0) =>
    fetchAPI<VersionPerformance[]>(`/leaderboard?min_hours=${minHours}`),
  getCurrentVersion: () => fetchAPI<CurrentVersion | null>('/current-version'),
};
