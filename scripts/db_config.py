"""Connexion DB Supabase marketing. Centralisée pour tous les scripts.

Règle Loys : jamais de MCP. Connexion directe psycopg2.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "db.ujgiurepjqbmoitnjhwj.supabase.co",
    "port": 5432,
    "user": "postgres",
    "password": "fzsA3XZKC1c7gREC",
    "database": "postgres",
    "sslmode": "require",
}


def get_conn(autocommit: bool = False):
    """Retourne une connexion psycopg2 brute. Préfère utiliser cursor() ci-dessous."""
    conn = psycopg2.connect(**DB_CONFIG)
    if autocommit:
        conn.autocommit = True
    return conn


def cursor(dict_rows: bool = True):
    """Context-like usage. Préférer with get_conn() as conn: with conn.cursor() ..."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor) if dict_rows else conn.cursor()
    return conn, cur
