-- Add leverage column to positions table to track the leverage used when opening each position
ALTER TABLE positions ADD COLUMN IF NOT EXISTS leverage NUMERIC DEFAULT 1.0;
