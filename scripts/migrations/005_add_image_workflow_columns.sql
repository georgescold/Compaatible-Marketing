-- Migration 005 : champs internes pour le workflow image sur mkt_tweets.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Objectif : permettre au pipeline d'ecriture de tweets de noter en interne
-- si une image serait pertinente (etape 1) sans avoir a choisir l'image
-- tout de suite. Le choix de l'image se fait plus tard (etape 3) en batch
-- au moment ou Loys clique sur le bouton "integrer les images".
--
-- IMPORTANT : ces colonnes sont INTERNES. Le CSV exporte vers Cortex ne
-- doit JAMAIS les contenir. Seul `media_url` (deja existant) part vers
-- Cortex avec l'URL publique HTTPS de l'image choisie.

ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS needs_image BOOLEAN DEFAULT FALSE;
ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS image_brief TEXT;
ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS image_id INTEGER REFERENCES mkt_images(id) ON DELETE SET NULL;
ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS image_chosen_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_mkt_tweets_needs_image ON mkt_tweets(needs_image) WHERE needs_image = TRUE;

COMMENT ON COLUMN mkt_tweets.needs_image IS
'Etape 1 : pose par l''IA au moment d''ecrire le tweet. TRUE si une image renforcerait l''emotion / la scene. INTERNE. Jamais exporte vers Cortex.';

COMMENT ON COLUMN mkt_tweets.image_brief IS
'Etape 1 : brief semantique de l''image souhaitee (ambiance, scene, emotion, palette). Sert a matcher contre mkt_images en etape 3. INTERNE. Jamais exporte.';

COMMENT ON COLUMN mkt_tweets.image_id IS
'Etape 3 : remplie quand Loys lance le batch "integrer les images". Reference l''image choisie dans mkt_images. INTERNE (sert a tracer le choix, pas a Cortex).';

COMMENT ON COLUMN mkt_tweets.image_chosen_at IS
'Etape 3 : timestamp de quand l''image a ete choisie. INTERNE.';
