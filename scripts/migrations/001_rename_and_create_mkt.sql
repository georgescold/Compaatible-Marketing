-- Migration 001 : préfixe mkt_ pour cohérence + tables tweets/runs/personas
-- Tout ce qui touche au marketing est préfixé `mkt_` pour bien séparer des tables blogs.
-- Idempotent : utilise IF NOT EXISTS partout sauf le RENAME (gardé manuel pour vérifier).

-- 1. Renommer la table images existante (créée en session 1, contient 8 rows)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='images')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='mkt_images')
    THEN
        ALTER TABLE images RENAME TO mkt_images;
        -- Renommer les indexes pour cohérence
        ALTER INDEX IF EXISTS idx_images_compaatible_fit RENAME TO idx_mkt_images_compaatible_fit;
        ALTER INDEX IF EXISTS idx_images_image_type RENAME TO idx_mkt_images_image_type;
        ALTER INDEX IF EXISTS idx_images_subject_type RENAME TO idx_mkt_images_subject_type;
        ALTER INDEX IF EXISTS idx_images_emotions RENAME TO idx_mkt_images_emotions;
        ALTER INDEX IF EXISTS idx_images_ambiance RENAME TO idx_mkt_images_ambiance;
        ALTER INDEX IF EXISTS idx_images_setting RENAME TO idx_mkt_images_setting;
        ALTER INDEX IF EXISTS idx_images_colors RENAME TO idx_mkt_images_colors;
        ALTER INDEX IF EXISTS idx_images_suggested_avatars RENAME TO idx_mkt_images_suggested_avatars;
        ALTER INDEX IF EXISTS idx_images_filename RENAME TO idx_mkt_images_filename;
        RAISE NOTICE 'Table images renamed to mkt_images.';
    END IF;
END
$$;

-- 2. Personas émergentes (générées à partir des CSV uploadés)
-- Chaque persona est UNIQUE (first_name + backstory ne se dupliquent jamais).
CREATE TABLE IF NOT EXISTS mkt_personas_emerged (
    id              SERIAL PRIMARY KEY,
    first_name      TEXT NOT NULL UNIQUE,         -- unique pour éviter doublons
    age             INTEGER,
    bio_twitter     TEXT,                          -- ≤ 160 chars, format Twitter bio
    backstory       TEXT NOT NULL,                 -- histoire détaillée (5-15 lignes)
    avatar_id_primary   INTEGER CHECK (avatar_id_primary BETWEEN 1 AND 11),
    avatar_id_secondary INTEGER CHECK (avatar_id_secondary BETWEEN 1 AND 11),
    voice_signature TEXT,                          -- vocabulaire/tournures préférés (description libre)
    vocabulary_yes  TEXT[],                        -- mots qu'elle utilise volontiers
    vocabulary_no   TEXT[],                        -- mots qu'elle n'utiliserait jamais
    source_csv      TEXT,                          -- nom du CSV qui a fait émerger cette persona
    source_handle   TEXT,                          -- handle Twitter source (ex: soymbleu)
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_mkt_personas_avatar ON mkt_personas_emerged(avatar_id_primary);

COMMENT ON TABLE mkt_personas_emerged IS 'Personas féminines uniques générées à partir des CSV importés. Chacune incarne un avatar Compaatible.';
COMMENT ON COLUMN mkt_personas_emerged.first_name IS 'UNIQUE. Aucune persona ne peut avoir le même prénom qu''une autre.';

-- 3. Tweets adaptés (output du pipeline, prêts pour Cortex)
CREATE TABLE IF NOT EXISTS mkt_tweets (
    id              SERIAL PRIMARY KEY,
    persona_id      INTEGER REFERENCES mkt_personas_emerged(id) ON DELETE SET NULL,
    csv_run_id      INTEGER,                       -- FK vers mkt_csv_runs (ajoutée plus bas)

    -- Champs Cortex exacts
    content         TEXT NOT NULL,                 -- ≤ 280 chars (≤ 270 si emojis composés)
    media_url       TEXT,                          -- séparateur pipe |, max 4 URLs HTTPS publiques
    scheduled_at    TIMESTAMPTZ,                   -- NULL = Cortex décide
    thread_key      TEXT,                          -- même valeur = même thread, ordre = ordre INSERT
    thread_order    INTEGER,                       -- position dans le thread (1, 2, 3...)

    -- Contexte de génération
    source_text     TEXT,                          -- tweet original (avant traduction)
    source_lang     TEXT,                          -- es, en, fr, etc.
    translation_fr  TEXT,                          -- traduction brute FR
    hook_pattern    TEXT,                          -- lucid_statement, confession, intimate_scene, poetic, etc.
    integration_strategy TEXT,                     -- 'none' | 'subtle_close' | 'natural_pivot' | 'direct_mention'
    reasoning       TEXT,                          -- pourquoi l'IA a fait ces choix
    char_count      INTEGER,                       -- pour vérification rapide

    -- Métriques source (héritées du CSV)
    source_likes    INTEGER,
    source_retweets INTEGER,
    source_views    INTEGER,
    source_url      TEXT,

    -- Statut (cycle de vie post-export)
    status          TEXT NOT NULL DEFAULT 'draft', -- 'draft' | 'approved' | 'exported' | 'posted_via_cortex'
    exported_at     TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mkt_tweets_persona ON mkt_tweets(persona_id);
CREATE INDEX IF NOT EXISTS idx_mkt_tweets_status ON mkt_tweets(status);
CREATE INDEX IF NOT EXISTS idx_mkt_tweets_thread ON mkt_tweets(thread_key, thread_order);
CREATE INDEX IF NOT EXISTS idx_mkt_tweets_csv_run ON mkt_tweets(csv_run_id);

COMMENT ON TABLE mkt_tweets IS 'Tweets adaptés au ton Compaatible, prêts à exporter au format Cortex.';

-- 4. Historique des exécutions de pipeline (un run par upload CSV)
CREATE TABLE IF NOT EXISTS mkt_csv_runs (
    id              SERIAL PRIMARY KEY,
    persona_id      INTEGER REFERENCES mkt_personas_emerged(id) ON DELETE SET NULL,
    source_csv_name TEXT NOT NULL,
    source_csv_size_kb INTEGER,
    source_tweets_count INTEGER,                   -- nombre de tweets dans le CSV source
    output_tweets_count INTEGER,                   -- nombre de tweets produits (après curation)
    threads_count   INTEGER,                       -- nombre de threads générés

    -- Modèles utilisés (snapshot)
    model_translation   TEXT,
    model_analysis      TEXT,
    model_adaptation    TEXT,

    -- Métriques coût
    input_tokens    INTEGER,
    cached_tokens   INTEGER,
    output_tokens   INTEGER,
    cost_usd        NUMERIC(10, 4),

    status          TEXT NOT NULL DEFAULT 'running', -- 'running' | 'completed' | 'failed' | 'cancelled'
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_mkt_csv_runs_persona ON mkt_csv_runs(persona_id);
CREATE INDEX IF NOT EXISTS idx_mkt_csv_runs_status ON mkt_csv_runs(status);
CREATE INDEX IF NOT EXISTS idx_mkt_csv_runs_started ON mkt_csv_runs(started_at);

COMMENT ON TABLE mkt_csv_runs IS 'Historique des exécutions du pipeline tweets : 1 run par upload CSV.';

-- 5. Foreign key tardive (mkt_tweets → mkt_csv_runs)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'mkt_tweets_csv_run_fk'
    ) THEN
        ALTER TABLE mkt_tweets
            ADD CONSTRAINT mkt_tweets_csv_run_fk
            FOREIGN KEY (csv_run_id) REFERENCES mkt_csv_runs(id) ON DELETE SET NULL;
    END IF;
END
$$;

-- 6. Settings (clé API + modèles configurés). Une seule row par user (singleton pratique).
CREATE TABLE IF NOT EXISTS mkt_settings (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    anthropic_api_key TEXT,
    model_translation TEXT DEFAULT 'claude-haiku-4-5-20251001',
    model_analysis    TEXT DEFAULT 'claude-haiku-4-5-20251001',
    model_adaptation  TEXT DEFAULT 'claude-sonnet-4-6',
    model_vision      TEXT DEFAULT 'claude-haiku-4-5-20251001',
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Insérer la row singleton si absente
INSERT INTO mkt_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE mkt_settings IS 'Settings du cockpit marketing (singleton, id=1). Clé API + modèles par tâche.';
