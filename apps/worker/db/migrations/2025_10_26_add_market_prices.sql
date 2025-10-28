-- Add market_prices table to store current market prices

CREATE TABLE IF NOT EXISTS market_prices (
    symbol TEXT PRIMARY KEY,
    price NUMERIC NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed with default values
INSERT INTO market_prices (symbol, price) VALUES
    ('BTC-USD', 0),
    ('ETH-USD', 0),
    ('SOL-USD', 0),
    ('DOGE-USD', 0),
    ('XRP-USD', 0)
ON CONFLICT (symbol) DO NOTHING;
