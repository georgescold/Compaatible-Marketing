-- Migration 006 : ajout de public_url a mkt_images.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Objectif : permettre au matching tweet -> image (etape 3) de remplir
-- mkt_tweets.media_url avec une URL HTTPS publique attendue par Cortex.
-- L'upload des images vers un host public (Supabase Storage, Imgur, CDN)
-- se fait separement ; cette colonne stocke juste l'URL resultante.
--
-- Tant que public_url est NULL pour une image, elle est skippee par le matcher
-- (impossible de l'envoyer a Cortex sans URL publique).

ALTER TABLE mkt_images ADD COLUMN IF NOT EXISTS public_url TEXT;

CREATE INDEX IF NOT EXISTS idx_mkt_images_public_url ON mkt_images(public_url) WHERE public_url IS NOT NULL;

COMMENT ON COLUMN mkt_images.public_url IS
'URL HTTPS publique de l''image (apres upload sur Supabase Storage / CDN / Imgur). Requis par Cortex pour pouvoir poster l''image. NULL = image pas encore uploadee, pas eligible au matching.';
