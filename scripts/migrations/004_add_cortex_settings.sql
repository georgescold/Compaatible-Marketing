-- Migration 004 : ajout des settings Cortex (token Bearer + URL de base).
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Objectif : permettre au cockpit d'envoyer les CSV produits directement vers
-- l'API Cortex (POST /api/v1/files) en un clic. Le token est créé dans l'UI
-- Cortex (/parametres/api) puis collé ici. Format : cortex_live_<32 chars>.

ALTER TABLE mkt_settings ADD COLUMN IF NOT EXISTS cortex_api_token TEXT;
ALTER TABLE mkt_settings ADD COLUMN IF NOT EXISTS cortex_base_url   TEXT;

COMMENT ON COLUMN mkt_settings.cortex_api_token IS
'Bearer token Cortex (cortex_live_xxx) créé dans l''UI Cortex /parametres/api. Utilisé par le cockpit pour POST /api/v1/files.';

COMMENT ON COLUMN mkt_settings.cortex_base_url IS
'Base URL de l''instance Cortex (ex: https://cortex.vercel.app). Sans slash final. Le cockpit y ajoute /api/v1/...';
