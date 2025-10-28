-- Add observation and action columns to model_chat table for expandable chat details

ALTER TABLE model_chat
  ADD COLUMN IF NOT EXISTS observation_prompt TEXT,
  ADD COLUMN IF NOT EXISTS action_response JSONB;

COMMENT ON COLUMN model_chat.observation_prompt IS 'Full formatted observation/prompt sent to the agent';
COMMENT ON COLUMN model_chat.action_response IS 'Full JSON response from the agent including all position decisions';
