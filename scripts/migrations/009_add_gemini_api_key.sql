-- Migration 009 : ajout de la clé API Gemini (Google) dans mkt_settings.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Objectif : permettre au cockpit d'utiliser Gemini 3.x Pro comme alternative
-- à Anthropic pour le copywriting / analyze / persona. Le routage entre
-- providers se fait sur le prefix du model id ("claude-*" vs "gemini-*").

ALTER TABLE mkt_settings ADD COLUMN IF NOT EXISTS gemini_api_key TEXT;

COMMENT ON COLUMN mkt_settings.gemini_api_key IS
'Clé API Google Gemini. Récupérée sur https://aistudio.google.com/apikey. Utilisée par cockpit/brain/gemini_client.py via le SDK google-genai.';
