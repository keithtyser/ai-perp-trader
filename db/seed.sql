-- seed data for local development and dashboard preview
-- DISABLED for clean perpsim start - uncomment to enable demo data

-- clear existing data
truncate table trades, positions, equity_snapshots, model_chat cascade;

-- -- insert sample trades
-- insert into trades (ts, symbol, side, qty, price, fee, client_id) values
--   (now() - interval '2 hours', 'BTC-PERP', 'buy', 0.001, 63500.0, 0.32, 'seed-1'),
--   (now() - interval '90 minutes', 'BTC-PERP', 'sell', 0.001, 63750.0, 0.32, 'seed-2'),
--   (now() - interval '60 minutes', 'ETH-PERP', 'buy', 0.01, 3100.0, 0.16, 'seed-3'),
--   (now() - interval '30 minutes', 'BTC-PERP', 'buy', 0.002, 63600.0, 0.64, 'seed-4');

-- -- insert sample positions
-- insert into positions (symbol, qty, avg_entry, unrealized_pl, updated_at) values
--   ('ETH-PERP', 0.01, 3100.0, 5.0, now()),
--   ('BTC-PERP', 0.002, 63600.0, 10.0, now());

-- -- insert equity snapshots for the last 2 hours
-- insert into equity_snapshots (ts, equity, cash, unrealized_pl)
-- select
--   generate_series(now() - interval '2 hours', now(), interval '5 minutes') as ts,
--   1000 + (extract(epoch from generate_series(now() - interval '2 hours', now(), interval '5 minutes'))::int % 100) as equity,
--   985.0 as cash,
--   15.0 as unrealized_pl;

-- -- insert sample model chat
-- insert into model_chat (ts, content, cycle_id) values
--   (now() - interval '2 hours', 'opened small long btc on breakout above 63500', 'cycle-1'),
--   (now() - interval '90 minutes', 'took profit on btc, +250 realized', 'cycle-2'),
--   (now() - interval '60 minutes', 'initiated eth position, tight stop at 3050', 'cycle-3'),
--   (now() - interval '30 minutes', 'added to btc position on pullback', 'cycle-4');

-- -- update metadata
-- update metadata set value = '15.5'::jsonb where key = 'pnl_all_time';
-- update metadata set value = '1.28'::jsonb where key = 'fees_paid_total';
-- update metadata set value = '-5.2'::jsonb where key = 'max_dd';
