-- Migration 010 : drapeaux editoriaux is_quote_trigger et is_clivant sur mkt_tweets.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Objectif : exposer dans le frontend cockpit les tweets que l'IA a marques comme
-- quote-trigger (doctrine ~1/10, cf prompts.py "Doctrine quote-trigger") ou comme
-- clivants (these incarnee qui divise, cf prompts.py "Evaluation clivante du thread").
-- Ces champs servent d'aide editoriale a la relecture : ils ne sont JAMAIS exportes
-- vers Cortex (Cortex ne connait que content/media_url/scheduled_at/thread_key).

ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS is_quote_trigger BOOLEAN DEFAULT FALSE;
ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS is_clivant BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_mkt_tweets_quote_trigger
  ON mkt_tweets(is_quote_trigger) WHERE is_quote_trigger = TRUE;
CREATE INDEX IF NOT EXISTS idx_mkt_tweets_clivant
  ON mkt_tweets(is_clivant) WHERE is_clivant = TRUE;

COMMENT ON COLUMN mkt_tweets.is_quote_trigger IS
'TRUE si l''IA a designe ce tweet comme quote-trigger (these incarnee qui invite au RT cite, doctrine ~1/10). INTERNE. Jamais exporte vers Cortex.';

COMMENT ON COLUMN mkt_tweets.is_clivant IS
'TRUE si l''IA a designe ce tweet comme portant un angle clivant (these incarnee qui divise). Souvent corrobore avec is_quote_trigger=TRUE. INTERNE. Jamais exporte.';
