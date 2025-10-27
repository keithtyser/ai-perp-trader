-- Multi-agent support migration
-- Adds agent_id to all relevant tables to support multiple trading agents

-- Create agents table to track registered agents
CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY,
  model_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  color TEXT NOT NULL, -- hex color for chart display
  enabled BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add agent_id to trades
ALTER TABLE trades ADD COLUMN IF NOT EXISTS agent_id TEXT;
CREATE INDEX IF NOT EXISTS idx_trades_agent_id ON trades(agent_id);

-- Create new positions table with agent support (old one has symbol as primary key)
-- We'll migrate data and then swap tables
CREATE TABLE IF NOT EXISTS positions_new (
  agent_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  qty NUMERIC NOT NULL,
  avg_entry NUMERIC NOT NULL,
  unrealized_pl NUMERIC NOT NULL DEFAULT 0,
  leverage NUMERIC,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (agent_id, symbol)
);

-- Add agent_id to equity_snapshots
-- Change primary key to (agent_id, ts)
CREATE TABLE IF NOT EXISTS equity_snapshots_new (
  agent_id TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  equity NUMERIC NOT NULL,
  cash NUMERIC NOT NULL,
  unrealized_pl NUMERIC NOT NULL DEFAULT 0,
  realized NUMERIC NOT NULL DEFAULT 0,
  fees NUMERIC NOT NULL DEFAULT 0,
  funding NUMERIC NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (agent_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_equity_snapshots_new_agent_ts ON equity_snapshots_new(agent_id, ts DESC);

-- Add agent_id to model_chat
ALTER TABLE model_chat ADD COLUMN IF NOT EXISTS agent_id TEXT;
CREATE INDEX IF NOT EXISTS idx_chat_agent_id ON model_chat(agent_id, ts DESC);

-- Create new metadata table with agent support
CREATE TABLE IF NOT EXISTS agent_metadata (
  agent_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (agent_id, key)
);

-- Seed some default agents (you can modify these)
INSERT INTO agents (agent_id, model_name, display_name, color, enabled) VALUES
  ('claude-sonnet-4.5', 'anthropic/claude-sonnet-4.5', 'Claude Sonnet 4.5', '#FF6B6B', true),
  ('gemini-2.5-pro', 'google/gemini-2.5-pro', 'Gemini 2.5 Pro', '#4ECDC4', true),
  ('qwen3-max', 'qwen/qwen3-max', 'Qwen3 Max', '#95E1D3', true),
  ('deepseek-v3.1', 'deepseek/deepseek-chat-v3.1', 'DeepSeek Chat V3.1', '#6C5CE7', true),
  ('grok-4', 'x-ai/grok-4', 'Grok 4', '#FD79A8', true),
  ('gpt-5', 'openai/gpt-5', 'GPT 5', '#00B894', true)
ON CONFLICT (agent_id) DO NOTHING;

-- Migration helper: If you have existing data, you can assign it to a default agent
-- UPDATE trades SET agent_id = 'claude-sonnet-4.5' WHERE agent_id IS NULL;
-- INSERT INTO positions_new SELECT 'claude-sonnet-4.5', symbol, qty, avg_entry, unrealized_pl, NULL, updated_at FROM positions;
-- INSERT INTO equity_snapshots_new SELECT 'claude-sonnet-4.5', ts, equity, cash, unrealized_pl, 0, 0, 0, created_at FROM equity_snapshots;
-- UPDATE model_chat SET agent_id = 'claude-sonnet-4.5' WHERE agent_id IS NULL;

-- After migration, you would drop old tables and rename new ones:
-- DROP TABLE positions;
-- ALTER TABLE positions_new RENAME TO positions;
-- DROP TABLE equity_snapshots;
-- ALTER TABLE equity_snapshots_new RENAME TO equity_snapshots;

-- Initialize metadata for each agent
INSERT INTO agent_metadata (agent_id, key, value)
SELECT agent_id, 'pnl_all_time', '0'::jsonb FROM agents
ON CONFLICT DO NOTHING;

INSERT INTO agent_metadata (agent_id, key, value)
SELECT agent_id, 'fees_paid_total', '0'::jsonb FROM agents
ON CONFLICT DO NOTHING;

INSERT INTO agent_metadata (agent_id, key, value)
SELECT agent_id, 'max_dd', '0'::jsonb FROM agents
ON CONFLICT DO NOTHING;

INSERT INTO agent_metadata (agent_id, key, value)
SELECT agent_id, 'last_error', '""'::jsonb FROM agents
ON CONFLICT DO NOTHING;
