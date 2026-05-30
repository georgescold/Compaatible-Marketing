-- Migration 011 : drapeau compaatible_promo sur mkt_csv_runs.
-- Idempotent (ADD COLUMN IF NOT EXISTS). Aucun touch sur les tables blogs.
--
-- Objectif : permettre de lancer un run (ou une extension) en mode "sans pub
-- Compaatible". Quand compaatible_promo = FALSE, l'avatar ecrit purement sa vie
-- quotidienne / ses experiences dans sa voix, avec ZERO mention nominale
-- "Compaatible", ZERO URL compaatible.com (blog inclus) et ZERO allusion produit.
-- Quand TRUE (defaut, comportement historique), la doctrine plancher/plafond
-- 10-15% de mentions s'applique comme avant.
--
-- Le flag est stocke sur le run pour qu'il persiste a travers les reprises,
-- extensions et extensions chainees, et qu'il s'affiche sur la page run.
-- DEFAULT TRUE => tous les runs existants gardent le comportement actuel.

ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS compaatible_promo BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN mkt_csv_runs.compaatible_promo IS
'TRUE (defaut) : doctrine mentions Compaatible 10-15% active. FALSE : run "sans pub", aucune mention nominale, aucune URL compaatible.com, aucune allusion produit ; pure incarnation de la voix de la persona.';
