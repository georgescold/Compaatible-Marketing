-- Migration 007 : pause/resume du copywriting tweets.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Permet d'interrompre un run en plein milieu du stage copywriting (entre deux
-- chunks de 20 tweets) et de le reprendre plus tard, eventuellement avec un
-- modele d'adaptation different (les chunks deja generes restent en DB,
-- seuls les chunks restants sont relances).
--
-- Colonnes ajoutees :
--   - status='paused' : nouveau statut (validation : status IN
--     ('running','completed','failed','paused')). On ne touche pas a la
--     contrainte CHECK existante si elle ne mentionne pas explicitement les
--     statuts ; sinon il faudra l'ajuster a la main.
--   - pause_state_json : snapshot {next_chunk_idx, total_chunks, mode} pour
--     savoir ou reprendre.

ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS pause_state_json JSONB;

COMMENT ON COLUMN mkt_csv_runs.pause_state_json IS
'Snapshot de pause durant le stage copywriting : {next_chunk_idx:int, total_chunks:int, mode:"copywriting"|"extension"}. NULL hors etat paused. Utilise par /resume-paused pour relancer le copywriting uniquement sur les chunks restants.';
