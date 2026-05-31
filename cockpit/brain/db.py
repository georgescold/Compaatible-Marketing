"""Connexion DB Supabase marketing. Wrapper autour de psycopg2.

Règle absolue Loys : jamais MCP, jamais toucher aux tables non-mkt_ (blogs).
"""
from __future__ import annotations
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

from config import Config


def get_conn(autocommit: bool = False):
    conn = psycopg2.connect(**Config.DB_CONFIG)
    if autocommit:
        conn.autocommit = True
    return conn


@contextmanager
def cursor(dict_rows: bool = True, autocommit: bool = False):
    """Context manager : with cursor() as cur: ..."""
    conn = get_conn(autocommit=autocommit)
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor) if dict_rows else conn.cursor()
        yield cur
        if not autocommit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def get_settings() -> dict:
    """Retourne la row singleton mkt_settings, ou des defaults si la table n'existe pas encore."""
    try:
        with cursor() as cur:
            cur.execute("SELECT * FROM mkt_settings WHERE id=1")
            row = cur.fetchone()
            if row:
                return dict(row)
    except psycopg2.errors.UndefinedTable:
        pass
    # Defaults si la migration n'a pas tourné
    return {
        "id": 1,
        "anthropic_api_key": None,
        "gemini_api_key": None,
        "model_translation": "claude-haiku-4-5-20251001",
        "model_analysis": "claude-haiku-4-5-20251001",
        "model_adaptation": "claude-sonnet-4-6",
        "model_vision": "claude-haiku-4-5-20251001",
        "model_image_association": "claude-haiku-4-5-20251001",
    }


def update_settings(**fields) -> dict:
    """Met à jour la row singleton avec les champs fournis. Retourne la row à jour."""
    if not fields:
        return get_settings()

    set_clauses = ", ".join(f"{k} = %({k})s" for k in fields)
    fields["id"] = 1

    with cursor() as cur:
        cur.execute(
            f"UPDATE mkt_settings SET {set_clauses}, updated_at = NOW() WHERE id = 1 RETURNING *",
            fields,
        )
        row = cur.fetchone()
        return dict(row) if row else get_settings()


def check_db_ready() -> tuple[bool, str]:
    """Teste la connexion DB et la présence des tables mkt_*. Retourne (ok, message)."""
    try:
        with cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name LIKE 'mkt_%'
                """
            )
            row = cur.fetchone()
            n = row["n"]
            if n == 0:
                return False, "Connexion DB OK mais aucune table mkt_* trouvée. Lance la migration : `python scripts/run_migration.py 001_rename_and_create_mkt.sql`"
            return True, f"DB OK : {n} tables mkt_* présentes."
    except Exception as e:
        return False, f"DB inaccessible : {e}"
