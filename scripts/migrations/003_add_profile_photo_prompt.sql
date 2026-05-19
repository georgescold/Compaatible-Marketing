-- Migration 003 : ajout du champ profile_photo_prompt à mkt_personas_emerged.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Objectif : stocker un prompt prêt à copier-coller dans un générateur d'image
-- (Midjourney, DALL-E, Stable Diffusion) pour produire la photo de profil Twitter
-- de la persona, en cohérence avec sa backstory et sa voix.

ALTER TABLE mkt_personas_emerged ADD COLUMN IF NOT EXISTS profile_photo_prompt TEXT;

COMMENT ON COLUMN mkt_personas_emerged.profile_photo_prompt IS
'Prompt prêt à coller dans un générateur d''image pour produire la photo de profil Twitter de la persona. Décrit le sujet, l''âge, l''ambiance, le cadrage, la lumière, les vêtements et l''expression, en cohérence avec la backstory.';
