"""Entry point du cockpit marketing Compaatible.

Lance Flask. Le `.bat` ouvre le navigateur sur http://localhost:5000.

IMPORTANT : on désactive le reloader Flask. Le pipeline tourne en background thread ;
un reload tue ce thread en plein appel API (perte d'argent + run cassé). Pour appliquer
des changements de code, redémarrer manuellement (Ctrl+C puis relancer).
"""
from flask import Flask

from config import Config
from routes import api, api_keys, dashboard, settings, tweets, images, knowledge, personas


def ensure_schema() -> None:
    """Migrations idempotentes au démarrage : ajoute les colonnes nécessaires aux features récentes.

    Ne touche jamais aux tables externes (blogs). Si la DB n'est pas joignable, ignore silencieusement.
    """
    from brain import db as db_mod
    try:
        with db_mod.cursor() as cur:
            cur.execute("""
                ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS archived_csv_path TEXT;
                ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS max_source_tweets INT;
                ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS parent_run_id INT;
                ALTER TABLE mkt_csv_runs ADD COLUMN IF NOT EXISTS health_check_json JSONB;
                ALTER TABLE mkt_tweets ADD COLUMN IF NOT EXISTS adaptation_level TEXT;

                CREATE TABLE IF NOT EXISTS mkt_api_keys (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    scopes TEXT[] NOT NULL DEFAULT ARRAY['images:write','images:read']::TEXT[],
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_used_at TIMESTAMPTZ,
                    revoked_at TIMESTAMPTZ,
                    request_count INT NOT NULL DEFAULT 0,
                    notes TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mkt_api_keys_hash ON mkt_api_keys(key_hash) WHERE revoked_at IS NULL;
            """)
        print("[startup] Schema verifie (mkt_csv_runs + mkt_tweets.adaptation_level + mkt_api_keys).", flush=True)
    except Exception as e:
        print(f"[startup] Verification schema ignoree : {e}", flush=True)


def cleanup_orphan_runs() -> None:
    """Au démarrage, marquer comme 'failed' tous les runs encore en 'running' dans la DB.

    Ils sont forcément orphelins (le thread qui les portait est mort avec le serveur).
    Évite que la page de run reste bloquée indéfiniment sur "running".
    """
    from brain import db as db_mod
    try:
        with db_mod.cursor() as cur:
            cur.execute(
                "UPDATE mkt_csv_runs SET status='failed', current_stage='failed', "
                "error_message=COALESCE(error_message, 'Serveur redémarré pendant le run · thread perdu') "
                "WHERE status='running' RETURNING id"
            )
            ids = [r["id"] for r in cur.fetchall()]
            if ids:
                print(f"[startup] Cleanup runs orphelins : {len(ids)} run(s) marques 'failed' ({', '.join(str(i) for i in ids)})", flush=True)
    except Exception as e:
        print(f"[startup] Cleanup runs orphelins ignore : {e}", flush=True)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB : CSV tweets + uploads images batch via API

    # Register blueprints
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(tweets.bp)
    app.register_blueprint(images.bp)
    app.register_blueprint(knowledge.bp)
    app.register_blueprint(api_keys.bp)
    app.register_blueprint(personas.bp)
    app.register_blueprint(api.bp)

    # Sidebar counts + indicateurs runs en cours (rendus dans base.html).
    # Permet à l'user de naviguer librement en gardant la trace de ce qui tourne.
    @app.context_processor
    def sidebar_counts():
        from brain import db as db_mod, run_state, image_batch_state
        tweets_n = images_n = 0
        try:
            with db_mod.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM mkt_tweets")
                tweets_n = cur.fetchone()["n"]
                cur.execute("SELECT COUNT(*) AS n FROM mkt_images")
                images_n = cur.fetchone()["n"]
        except Exception:
            pass

        active_tweet_runs = run_state.list_active()
        active_image_batches = image_batch_state.list_active()

        return {
            "tweets_count": tweets_n,
            "images_count": images_n,
            "tweets_running": len(active_tweet_runs),
            "images_running": len(active_image_batches),
            "active_tweet_run_ids": active_tweet_runs,
            "active_image_batch_ids": active_image_batches,
        }

    return app


if __name__ == "__main__":
    ensure_schema()
    cleanup_orphan_runs()
    app = create_app()
    print(f"\n  Cockpit marketing Compaatible")
    print(f"  http://localhost:{Config.PORT}")
    print(f"  Reloader desactive : edite ton code puis Ctrl+C / relance pour appliquer.\n", flush=True)
    # use_reloader=False : evite que le pipeline en background soit tue par un auto-restart.
    # Le debugger reste actif (tracebacks dans la console et /__debugger__).
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG, use_reloader=False)
