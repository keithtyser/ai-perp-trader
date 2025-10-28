-- Add entry_time to positions table to track when positions were opened
-- This helps prevent rapid position flipping and enforces minimum holding periods

ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_time TIMESTAMPTZ;
ALTER TABLE positions_new ADD COLUMN IF NOT EXISTS entry_time TIMESTAMPTZ;

-- For existing positions, set entry_time to updated_at (approximation)
UPDATE positions SET entry_time = updated_at WHERE entry_time IS NULL;
UPDATE positions_new SET entry_time = updated_at WHERE entry_time IS NULL;

-- Add index for querying by entry_time
CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_time);
CREATE INDEX IF NOT EXISTS idx_positions_new_entry_time ON positions_new(entry_time);
