-- hyperliquid agent database schema
-- postgres 14+ or supabase compatible

-- trades: record of all filled orders
create table if not exists trades (
  id bigserial primary key,
  ts timestamptz not null default now(),
  symbol text not null,
  side text check (side in ('buy', 'sell')) not null,
  qty numeric not null,
  price numeric not null,
  fee numeric not null default 0,
  client_id text unique,
  entry_reason text,  -- justification for opening this position
  exit_reason text,   -- justification for closing this position
  created_at timestamptz not null default now()
);

create index if not exists idx_trades_ts on trades(ts desc);
create index if not exists idx_trades_symbol on trades(symbol);

-- positions: current open positions
create table if not exists positions (
  symbol text primary key,
  qty numeric not null,
  avg_entry numeric not null,
  unrealized_pl numeric not null default 0,
  exit_plan jsonb,
  leverage numeric default 1.0,
  entry_time timestamptz,
  entry_justification text,  -- why this position was opened
  updated_at timestamptz not null default now()
);

-- equity_snapshots: minute-level equity curve
create table if not exists equity_snapshots (
  ts timestamptz primary key,
  equity numeric not null,
  cash numeric not null,
  unrealized_pl numeric not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_equity_ts on equity_snapshots(ts desc);

-- model_chat: decision notes from the llm
create table if not exists model_chat (
  id bigserial primary key,
  ts timestamptz not null default now(),
  content text not null,
  cycle_id text,
  created_at timestamptz not null default now()
);

create index if not exists idx_chat_ts on model_chat(ts desc);

-- metadata: key-value store for agent state
create table if not exists metadata (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

-- insert initial metadata
insert into metadata (key, value) values
  ('pnl_all_time', '0'::jsonb),
  ('fees_paid_total', '0'::jsonb),
  ('max_dd', '0'::jsonb),
  ('last_error', '""'::jsonb)
on conflict (key) do nothing;
