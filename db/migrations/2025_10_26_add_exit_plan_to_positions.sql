-- Add exit_plan column to positions table
ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_plan JSONB;
