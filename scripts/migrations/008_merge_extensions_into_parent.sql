-- Migration 008 : fusion des extensions dans le run parent.
-- Idempotent (ADD COLUMN IF NOT EXISTS, garde-fous sur le backfill).
-- Aucun touch sur les tables blogs.
--
-- Contexte : avant cette migration, chaque "Prolonger de N tweets" creait
-- un nouveau run mkt_csv_runs avec parent_run_id pointant sur le run d'origine.
-- Resultat : les tweets etaient eparpilles sur plusieurs runs, le download
-- CSV du run parent ne donnait que les tweets initiaux. Confus pour l'user.
--
-- Apres : tous les tweets (originaux + extensions) vivent sous le csv_run_id
-- du run PARENT. Une colonne extension_idx (NULL = original, 1, 2, ... =
-- batch d'extension chronologique) permet de retracer l'origine sans
-- multiplier les rows mkt_csv_runs.
--
-- Etapes :
-- 1. Ajout colonne mkt_tweets.extension_idx
-- 2. Backfill : pour chaque run dont parent_run_id IS NOT NULL et
--    source_csv_name commence par '[extension', on transfere ses tweets au
--    parent en numerotant extension_idx selon l'ordre chronologique des runs
--    enfants pour ce parent
-- 3. Mise a jour du parent : output_tweets_count cumule, cost_usd cumule
-- 4. Suppression des rows mkt_csv_runs des extensions devenues vides

ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS extension_idx INTEGER;

COMMENT ON COLUMN mkt_tweets.extension_idx IS
'NULL = tweet du run original. 1, 2, ... = batch d''extension chronologique. Permet de tracer l''origine sans multiplier les rows mkt_csv_runs.';

CREATE INDEX IF NOT EXISTS idx_mkt_tweets_extension_idx ON mkt_tweets(csv_run_id, extension_idx)
  WHERE extension_idx IS NOT NULL;

-- Backfill : transferer les tweets des extensions vers le parent
DO $$
DECLARE
  parent_id INTEGER;
  ext_run RECORD;
  next_idx INTEGER;
  n_moved INTEGER;
  total_cost NUMERIC;
  total_input BIGINT;
  total_cached BIGINT;
  total_output BIGINT;
BEGIN
  -- Parents qui ont au moins un enfant '[extension'
  FOR parent_id IN
    SELECT DISTINCT parent_run_id
    FROM mkt_csv_runs
    WHERE parent_run_id IS NOT NULL
      AND source_csv_name LIKE '[extension%'
  LOOP
    next_idx := COALESCE((SELECT MAX(extension_idx) FROM mkt_tweets WHERE csv_run_id = parent_id), 0) + 1;

    FOR ext_run IN
      SELECT id, output_tweets_count, cost_usd, input_tokens, cached_tokens, output_tokens
      FROM mkt_csv_runs
      WHERE parent_run_id = parent_id
        AND source_csv_name LIKE '[extension%'
      ORDER BY started_at ASC NULLS LAST, id ASC
    LOOP
      -- Move tweets vers le parent avec extension_idx
      UPDATE mkt_tweets
      SET csv_run_id = parent_id, extension_idx = next_idx
      WHERE csv_run_id = ext_run.id;
      GET DIAGNOSTICS n_moved = ROW_COUNT;

      RAISE NOTICE 'Migration 008 : run #% (extension N°%) -> parent #% · % tweets deplaces',
        ext_run.id, next_idx, parent_id, n_moved;

      next_idx := next_idx + 1;
    END LOOP;

    -- Cumul des metriques sur le parent
    SELECT
      COALESCE(SUM(cost_usd), 0),
      COALESCE(SUM(input_tokens), 0),
      COALESCE(SUM(cached_tokens), 0),
      COALESCE(SUM(output_tokens), 0)
    INTO total_cost, total_input, total_cached, total_output
    FROM mkt_csv_runs
    WHERE id = parent_id OR (parent_run_id = parent_id AND source_csv_name LIKE '[extension%');

    UPDATE mkt_csv_runs
    SET cost_usd = total_cost,
        input_tokens = total_input,
        cached_tokens = total_cached,
        output_tokens = total_output,
        output_tweets_count = (SELECT COUNT(*) FROM mkt_tweets WHERE csv_run_id = parent_id),
        threads_count = (SELECT COUNT(DISTINCT thread_key) FROM mkt_tweets
                         WHERE csv_run_id = parent_id AND thread_key IS NOT NULL)
    WHERE id = parent_id;

    -- Casser les liens parent_run_id qui pointaient sur les enfants extension
    UPDATE mkt_csv_runs
    SET parent_run_id = NULL
    WHERE parent_run_id IN (
      SELECT id FROM mkt_csv_runs
      WHERE parent_run_id = parent_id AND source_csv_name LIKE '[extension%'
    );

    -- Supprimer les rows extension devenues vides
    DELETE FROM mkt_csv_runs
    WHERE parent_run_id = parent_id
      AND source_csv_name LIKE '[extension%';
  END LOOP;

  RAISE NOTICE 'Migration 008 : backfill termine.';
END $$;
