"""Client HTTP pour l'API Cortex (Hub Fichiers).

Cortex = moteur d'automation Twitter externe (hosted Vercel). Le cockpit
produit un CSV au format `content,media_url,scheduled_at,thread_key` et le
pousse ici via `POST /api/v1/files` (multipart). Cortex affiche ensuite le
fichier dans son UI /fichiers en attente d'attribution manuelle à une persona.

Auth : Bearer token `cortex_live_<32>` créé dans l'UI Cortex /parametres/api,
collé dans les Settings du cockpit, stocké dans `mkt_settings.cortex_api_token`.

Voir spec complète : memory/reference_cortex_api.md.
"""
from __future__ import annotations
from typing import Any

import requests

from brain.db import get_settings


CORTEX_TIMEOUT = 30.0  # secondes


class CortexConfigError(RuntimeError):
    """Token ou base URL Cortex absent / mal configuré."""


class CortexError(RuntimeError):
    """Erreur retournée par l'API Cortex (4xx / 5xx). `payload` contient le JSON renvoyé si dispo."""

    def __init__(self, message: str, status: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


def _resolve_config() -> tuple[str, str]:
    """Retourne (base_url_sans_slash, bearer_token). Lève CortexConfigError si incomplet."""
    s = get_settings()
    token = (s.get("cortex_api_token") or "").strip()
    base = (s.get("cortex_base_url") or "").strip().rstrip("/")
    if not token:
        raise CortexConfigError("Token Cortex absent. Configure-le dans /settings.")
    if not base:
        raise CortexConfigError("URL Cortex absente. Configure-la dans /settings (ex: https://cortex.vercel.app).")
    if not base.startswith(("http://", "https://")):
        raise CortexConfigError(f"URL Cortex invalide : `{base}` (doit commencer par https://).")
    return base, token


def _headers(token: str, content_type: str | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if content_type:
        h["Content-Type"] = content_type
    return h


def is_configured() -> bool:
    try:
        _resolve_config()
        return True
    except CortexConfigError:
        return False


def ping() -> dict[str, Any]:
    """GET /api/v1/ping. Retourne le payload Cortex `{ok, user_id, auth_source}`."""
    base, token = _resolve_config()
    url = f"{base}/api/v1/ping"
    try:
        r = requests.get(url, headers=_headers(token), timeout=CORTEX_TIMEOUT)
    except requests.RequestException as e:
        raise CortexError(f"Connexion Cortex impossible : {e}") from e

    if r.status_code == 200:
        try:
            return r.json()
        except ValueError:
            raise CortexError("Réponse Cortex non-JSON sur /ping.", status=200)

    payload = _safe_json(r)
    if r.status_code == 401:
        raise CortexError("Token Cortex invalide ou révoqué.", status=401, payload=payload)
    raise CortexError(f"Cortex /ping a renvoyé HTTP {r.status_code}.", status=r.status_code, payload=payload)


def upload_csv(csv_bytes: bytes, filename: str) -> dict[str, Any]:
    """POST /api/v1/files en multipart. Retourne le payload Cortex (file + preview).

    Lève CortexError sur 4xx/5xx avec status + payload pour que l'UI affiche
    `parse_summary.fatalError` proprement.
    """
    base, token = _resolve_config()
    url = f"{base}/api/v1/files"
    files = {"file": (filename, csv_bytes, "text/csv")}

    try:
        r = requests.post(url, headers=_headers(token), files=files, timeout=CORTEX_TIMEOUT)
    except requests.RequestException as e:
        raise CortexError(f"Connexion Cortex impossible : {e}") from e

    payload = _safe_json(r)
    if r.status_code in (200, 201):
        return payload

    msg = _extract_error_message(payload) or f"HTTP {r.status_code}"
    if r.status_code == 400:
        raise CortexError(f"CSV rejeté par Cortex : {msg}", status=400, payload=payload)
    if r.status_code == 401:
        raise CortexError("Token Cortex invalide ou révoqué.", status=401, payload=payload)
    if r.status_code == 413:
        raise CortexError("Fichier trop gros (> 8 MB).", status=413, payload=payload)
    if r.status_code == 415:
        raise CortexError("Type MIME refusé par Cortex (attendu multipart ou JSON).", status=415, payload=payload)
    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After", "60")
        raise CortexError(f"Rate limit Cortex atteint (réessaie dans {retry_after}s).", status=429, payload=payload)
    raise CortexError(f"Cortex /files a renvoyé HTTP {r.status_code} : {msg}", status=r.status_code, payload=payload)


def _safe_json(r: requests.Response) -> dict:
    try:
        return r.json() if r.content else {}
    except ValueError:
        return {}


def _extract_error_message(payload: dict) -> str | None:
    """Tente d'extraire un message d'erreur lisible du payload Cortex.

    Cortex renvoie typiquement soit `{error: "..."}`, soit
    `{parse_summary: {fatalError: "..."}}`. On tente les deux.
    """
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("error"), str):
        return payload["error"]
    ps = payload.get("parse_summary")
    if isinstance(ps, dict) and isinstance(ps.get("fatalError"), str):
        return ps["fatalError"]
    if isinstance(payload.get("message"), str):
        return payload["message"]
    return None
