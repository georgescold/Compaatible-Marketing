-- Migration 012 : modele dedie a l'association image<->tweet (matching assiste IA).
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Contexte : jusqu'ici un seul modele "vision" (model_vision) servait au
-- TRAITEMENT des images (description/classification a l'upload). L'ASSOCIATION
-- (appariement image<->tweet) etait 100% algorithmique. On ajoute un modele
-- distinct, selectionnable dans les parametres, utilise UNIQUEMENT quand le
-- "matching assiste par IA" est active au lancement : l'algo pre-selectionne un
-- top N de candidats, ce modele tranche. Sans l'option, aucun appel modele.
--
-- model_vision est conserve tel quel (juste relabellise en UI : "Traitement des
-- images"). DEFAULT Haiku 4.5 : leger et peu cher, suffisant pour un choix
-- parmi quelques candidats deja pre-filtres.

ALTER TABLE mkt_settings ADD COLUMN IF NOT EXISTS model_image_association TEXT DEFAULT 'claude-haiku-4-5-20251001';

COMMENT ON COLUMN mkt_settings.model_image_association IS
'Modele utilise pour l''association image<->tweet quand le matching assiste par IA est active (re-rank d''un top N de candidats pre-filtres par l''algo). Sans l''option, le matching reste algorithmique et n''appelle aucun modele.';
