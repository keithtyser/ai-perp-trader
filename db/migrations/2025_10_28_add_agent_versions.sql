-- Agent version tracking for performance leaderboard
-- This tracks each deployment/version of the agent and its performance metrics

create table if not exists agent_versions (
  id bigserial primary key,
  version_tag text not null unique,  -- Semantic version: "v1.0.0", "v1.1.0", "v2.0.0-beta"
  description text,  -- Human-readable description of changes
  deployed_at timestamptz not null default now(),
  retired_at timestamptz,  -- When this version was replaced

  -- Snapshot of configuration at deployment
  config jsonb,  -- Store relevant config like model, trading backend, symbols, etc.

  created_at timestamptz not null default now()
);

create index if not exists idx_versions_deployed on agent_versions(deployed_at desc);
create index if not exists idx_versions_tag on agent_versions(version_tag);

-- Performance metrics per version (calculated periodically or on retirement)
create table if not exists version_performance (
  id bigserial primary key,
  version_id bigint not null references agent_versions(id) on delete cascade,

  -- Time period for these metrics
  period_start timestamptz not null,
  period_end timestamptz,

  -- Duration metrics
  duration_days numeric,  -- Total days active
  uptime_minutes numeric,  -- Actual running time
  total_cycles integer default 0,  -- Number of decision cycles

  -- Core performance metrics
  total_return_pct numeric not null default 0,  -- Total return %
  daily_return_pct numeric,  -- Average daily return %
  sharpe_ratio numeric,  -- Risk-adjusted returns
  max_drawdown_pct numeric,  -- Worst peak-to-trough decline

  -- Trading statistics
  total_trades integer not null default 0,
  trades_per_day numeric,  -- Average trades per day
  win_rate numeric,  -- % of winning trades
  profit_factor numeric,  -- avg_win / avg_loss
  avg_hold_time_minutes numeric,

  -- P&L breakdown
  realized_pnl numeric not null default 0,
  unrealized_pnl numeric not null default 0,
  total_fees numeric not null default 0,
  pnl_per_day numeric,  -- Average PnL per day

  -- Volume and activity
  total_volume numeric not null default 0,

  -- Equity tracking
  starting_equity numeric not null,
  ending_equity numeric not null,

  calculated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),

  -- Ensure one record per version
  unique(version_id)
);

create index if not exists idx_version_perf_version on version_performance(version_id);
create index if not exists idx_version_perf_sharpe on version_performance(sharpe_ratio desc nulls last);
create index if not exists idx_version_perf_return on version_performance(total_return_pct desc);

-- Track which version was active during which time periods
create table if not exists version_activity (
  id bigserial primary key,
  version_id bigint not null references agent_versions(id) on delete cascade,
  started_at timestamptz not null default now(),
  ended_at timestamptz,  -- NULL if currently active

  created_at timestamptz not null default now()
);

create index if not exists idx_version_activity_version on version_activity(version_id);
create index if not exists idx_version_activity_period on version_activity(started_at, ended_at);
create index if not exists idx_version_activity_active on version_activity(ended_at) where ended_at is null;

-- Add version tracking to existing tables (non-destructive)
alter table trades add column if not exists version_id bigint references agent_versions(id);
alter table model_chat add column if not exists version_id bigint references agent_versions(id);
alter table equity_snapshots add column if not exists version_id bigint references agent_versions(id);

create index if not exists idx_trades_version on trades(version_id);
create index if not exists idx_chat_version on model_chat(version_id);
create index if not exists idx_equity_version on equity_snapshots(version_id);
