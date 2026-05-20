"""Configuration centrale du cockpit. Lit le .env, expose les valeurs partout."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger .env depuis le dossier cockpit/
BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

# Racine du projet "Compaatible marketing" (parent de cockpit/)
PROJECT_ROOT = BASE_DIR.parent.resolve()


class Config:
    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    # Anthropic
    ANTHROPIC_API_KEY_ENV = os.getenv("ANTHROPIC_API_KEY", "")

    # Gemini (Google)
    GEMINI_API_KEY_ENV = os.getenv("GEMINI_API_KEY", "")

    # DB Supabase
    DB_CONFIG = {
        "host": os.getenv("MARKETING_DB_HOST", "db.ujgiurepjqbmoitnjhwj.supabase.co"),
        "port": int(os.getenv("MARKETING_DB_PORT", "5432")),
        "user": os.getenv("MARKETING_DB_USER", "postgres"),
        "password": os.getenv("MARKETING_DB_PASSWORD", ""),
        "database": os.getenv("MARKETING_DB_DATABASE", "postgres"),
        "sslmode": "require",
    }

    # Chemins importants
    KNOWLEDGE_DIR = PROJECT_ROOT / "Knowledges"
    # Source de vérité unique pour les avatars : le fichier complet (1399 lignes,
    # hook banks détaillés). Pas d'index résumé : la profondeur est nécessaire.
    AVATARS_FILE = PROJECT_ROOT / "Compaatible" / "Avatars Compaatible.md"
    IMAGES_DIR = PROJECT_ROOT / "Images"
    UPLOADS_DIR = BASE_DIR / "data" / "uploads"
    OUTPUTS_DIR = BASE_DIR / "data" / "outputs"

    # Modèles disponibles (UI dropdown). Le provider est routé par prefix du model id
    # dans cockpit/brain/llm_client.py : "claude-*" → Anthropic, "gemini-*" → Google.
    AVAILABLE_MODELS = [
        {"id": "claude-opus-4-7", "label": "Claude Opus 4.7 (le plus puissant)"},
        {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6 (équilibré, défaut copywriting)"},
        {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5 (rapide, défaut traduction/vision)"},
        {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro Preview (Google, meilleur rapport qualité/prix)"},
        {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash (Google, thinking · sweet spot qualité/prix)"},
        {"id": "gemini-3-flash", "label": "Gemini 3 Flash (Google, 4× moins cher que Pro, pas de thinking)"},
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash Lite (Google, ultra léger · 150k req/jour)"},
    ]
