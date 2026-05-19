-- Migration 002 : enrichissement de mkt_csv_runs avec le playbook et les stats source.
-- Idempotent (ADD COLUMN IF NOT EXISTS).
-- Aucun touch sur les tables blogs.

ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS playbook_json JSONB;
ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS source_stats_json JSONB;
ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS detected_language TEXT;
ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS source_handle TEXT;

-- Étape : ajout d'un champ "stage" pour suivre le pipeline en cours
ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS current_stage TEXT DEFAULT 'pending';
-- valeurs: 'pending' | 'parsing' | 'analyzing' | 'persona' | 'adapting' | 'validating' | 'completed' | 'failed'

COMMENT ON COLUMN mkt_csv_runs.playbook_json IS 'Playbook extrait du compte source : mécanismes identifiés (5-15), ranked par engagement.';
COMMENT ON COLUMN mkt_csv_runs.source_stats_json IS 'Stats brutes sur le CSV source : distributions likes, longueurs, ratios topics, etc.';
COMMENT ON COLUMN mkt_csv_runs.detected_language IS 'Langue dominante détectée (es, en, fr, etc.)';
COMMENT ON COLUMN mkt_csv_runs.source_handle IS 'Handle Twitter source extrait du CSV (ex: soymbleu)';

-- Tweets : on garde un lien vers le mécanisme du playbook qui a inspiré le tweet
ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS mechanism_applied TEXT;
COMMENT ON COLUMN mkt_tweets.mechanism_applied IS 'Nom du mécanisme du playbook source qui a inspiré ce tweet Compaatible.';
