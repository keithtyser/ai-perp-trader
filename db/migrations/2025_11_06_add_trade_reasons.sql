-- Migration: Add entry_reason and exit_reason to trades table
-- Date: 2025-11-06
-- Description: Add columns to track why positions were opened and closed

-- Add entry_reason column to trades if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'entry_reason'
    ) THEN
        ALTER TABLE trades ADD COLUMN entry_reason text;
    END IF;
END $$;

-- Add exit_reason column to trades if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'exit_reason'
    ) THEN
        ALTER TABLE trades ADD COLUMN exit_reason text;
    END IF;
END $$;

-- Add entry_justification column to positions table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'entry_justification'
    ) THEN
        ALTER TABLE positions ADD COLUMN entry_justification text;
    END IF;
END $$;

-- Add entry_justification column to positions_new table (if it exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'positions_new'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'positions_new' AND column_name = 'entry_justification'
        ) THEN
            ALTER TABLE positions_new ADD COLUMN entry_justification text;
        END IF;
    END IF;
END $$;
