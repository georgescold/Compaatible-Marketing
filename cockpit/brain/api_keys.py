"""Gestion des clés API Compaatible (auth des appels externes au cockpit).

La clé en clair n'est JAMAIS stockée : on garde un sha256 + un prefix d'affichage.
L'utilisateur ne peut voir la clé qu'une seule fois, à la création.

Format : `cmp_<32 chars base32>` (44 chars total).
"""
from __future__ import annotations
import hashlib
import secrets
from typing import Any

from brain import db


KEY_PREFIX = "cmp_"
DEFAULT_SCOPES = ["images:write", "images:read"]
PREFIX_DISPLAY_LEN = 12  # ex: "cmp_A7K9..." pour la liste


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _generate_key() -> str:
    # 32 caractères url-safe → 192 bits d'entropie
    body = secrets.token_urlsafe(24)  # ~32 chars
    return f"{KEY_PREFIX}{body}"


def create_key(name: str, scopes: list[str] | None = None, notes: str | None = None) -> dict[str, Any]:
    """Crée une nouvelle clé. Retourne {id, key_plaintext, prefix, name, scopes}.

    `key_plaintext` n'est retourné qu'ICI : impossible de la récupérer ensuite.
    """
    if not name or not name.strip():
        raise ValueError("Le nom de la clé est obligatoire.")
    name = name.strip()[:80]
    scopes = scopes or DEFAULT_SCOPES
    plaintext = _generate_key()
    key_hash = _hash(plaintext)
    key_prefix = plaintext[:PREFIX_DISPLAY_LEN]

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO mkt_api_keys (name, key_hash, key_prefix, scopes, notes) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id, name, key_prefix, scopes, created_at",
            (name, key_hash, key_prefix, scopes, notes),
        )
        row = dict(cur.fetchone())

    row["key_plaintext"] = plaintext
    return row


def list_keys(include_revoked: bool = True) -> list[dict[str, Any]]:
    where = "" if include_revoked else "WHERE revoked_at IS NULL"
    with db.cursor() as cur:
        cur.execute(
            f"SELECT id, name, key_prefix, scopes, created_at, last_used_at, "
            f"revoked_at, request_count, notes "
            f"FROM mkt_api_keys {where} ORDER BY created_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]


def revoke_key(key_id: int) -> bool:
    with db.cursor() as cur:
        cur.execute(
            "UPDATE mkt_api_keys SET revoked_at = NOW() "
            "WHERE id = %s AND revoked_at IS NULL RETURNING id",
            (key_id,),
        )
        return cur.fetchone() is not None


def delete_key(key_id: int) -> bool:
    with db.cursor() as cur:
        cur.execute("DELETE FROM mkt_api_keys WHERE id = %s RETURNING id", (key_id,))
        return cur.fetchone() is not None


def verify(key_plaintext: str) -> dict[str, Any] | None:
    """Vérifie une clé. Retourne la row (sans key_hash) si valide et non révoquée, sinon None.

    Touche `last_used_at` et incrémente `request_count`.
    """
    if not key_plaintext or not key_plaintext.startswith(KEY_PREFIX):
        return None
    key_hash = _hash(key_plaintext)
    with db.cursor() as cur:
        cur.execute(
            "UPDATE mkt_api_keys SET last_used_at = NOW(), request_count = request_count + 1 "
            "WHERE key_hash = %s AND revoked_at IS NULL "
            "RETURNING id, name, key_prefix, scopes, created_at, last_used_at, request_count",
            (key_hash,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def has_scope(key_row: dict, scope: str) -> bool:
    scopes = key_row.get("scopes") or []
    if "*" in scopes:
        return True
    return scope in scopes
