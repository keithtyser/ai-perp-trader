-- migration: add perpsim fields and config table
-- date: 2025-10-25

-- add realized, fees, funding fields to equity_snapshots
alter table equity_snapshots add column if not exists realized numeric default 0;
alter table equity_snapshots add column if not exists unrealized numeric default 0; -- rename for clarity
alter table equity_snapshots add column if not exists fees numeric default 0;
alter table equity_snapshots add column if not exists funding numeric default 0;

-- sim_config: configuration for perpsim
create table if not exists sim_config (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);

-- seed default sim config
insert into sim_config (key, value) values
  ('im', '0.05'),
  ('mm', '0.03'),
  ('max_leverage', '20'),
  ('slippage_bps', '1'),
  ('fee_bps', '2'),
  ('liq_penalty_bps', '5'),
  ('funding_mode', 'A')
on conflict (key) do nothing;

-- add sim metadata entries
insert into metadata (key, value) values
  ('sim_fees', '0'::jsonb),
  ('sim_funding', '0'::jsonb),
  ('sim_realized', '0'::jsonb)
on conflict (key) do nothing;
