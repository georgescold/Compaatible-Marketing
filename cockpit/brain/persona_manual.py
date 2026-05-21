"""Création manuelle de persona depuis l'onglet Personas (pas de CSV source).

Différence vs `persona_generator.py` :
- Pas de tweets sources à observer → la voix doit être INVENTÉE depuis le couple
  (genre × âge × avatar choisi × notes utilisateur libres).
- Le LLM reçoit la fiche complète de l'avatar choisi (extraite de
  `Compaatible/Avatars Compaatible.md`) et doit en déduire une persona cohérente.
- En plus de la persona, génère 3 tweets de preview en un seul appel : un isolé,
  un thread de 3 messages avec mention Compaatible en T2/T3, et un quote-trigger.
  Les preview servent à valider la voix AVANT l'insert DB.

Stateful : la persona N'EST PAS insérée par cette fonction. Le caller décide
(via UI) de sauver ou de régénérer.
"""
from __future__ import annotations
import json
from typing import Any

from brain import prompts, llm_client, db, avatars_catalog
from brain.source_analyzer import parse_json_response


def _existing_first_names() -> list[str]:
    with db.cursor() as cur:
        cur.execute("SELECT first_name FROM mkt_personas_emerged ORDER BY first_name")
        return [r["first_name"] for r in cur.fetchall()]


def _build_user_message(
    gender: str,
    age: int,
    avatar_primary: dict,
    avatar_secondary: dict | None,
    first_name_hint: str | None,
    notes: str | None,
) -> str:
    existing = _existing_first_names()
    existing_block = (
        "\n".join(f"- {n}" for n in existing) if existing else "(aucune persona existante)"
    )

    parts = [
        "## PRESETS UTILISATEUR (non négociables)\n",
        f"- **Genre** : {gender}",
        f"- **Âge** : {age} ans",
        f"- **Avatar primaire** : Avatar {avatar_primary['id']} — {avatar_primary['name']}",
    ]
    if avatar_secondary:
        parts.append(
            f"- **Avatar secondaire** : Avatar {avatar_secondary['id']} — {avatar_secondary['name']}"
        )
    if first_name_hint:
        parts.append(f"- **Prénom souhaité** : {first_name_hint} (utilise-le tel quel)")
    else:
        parts.append("- **Prénom** : libre de ton choix (cohérent avec genre + âge + contexte français)")
    if notes:
        parts.append(f"\n**Notes additionnelles de l'utilisateur** :\n{notes}")

    parts.append("\n## FICHE COMPLÈTE DE L'AVATAR PRIMAIRE\n")
    parts.append(avatar_primary["full_block"])

    if avatar_secondary:
        parts.append("\n## FICHE COMPLÈTE DE L'AVATAR SECONDAIRE\n")
        parts.append(avatar_secondary["full_block"])

    parts.append("\n## PRÉNOMS DÉJÀ UTILISÉS (à NE PAS dupliquer)\n")
    parts.append(existing_block)

    parts.append(
        "\n## TA MISSION\n\n"
        f"Crée une persona Compaatible **{gender}** de **{age} ans** qui incarne crédiblement "
        f"l'Avatar {avatar_primary['id']} ({avatar_primary['name']}). "
        "Puisqu'il n'y a pas de tweets sources à observer, tu **inventes** entièrement sa voix "
        "à partir de ce que dit la fiche avatar (psychologie, peurs, sa relation aux apps, ce qui "
        "le/la fait réagir), du genre, de l'âge, et des notes utilisateur si présentes.\n\n"
        "**Cohérence interne** : le prénom, la backstory, la bio, la voix doivent former un tout. "
        "Une introvertie de 27 ans dans le milieu de l'édition n'écrit pas comme un cadre de 36 ans "
        "à Paris. Sois précis sur le métier, le lieu, le parcours amoureux passé.\n\n"
        "**Voix** : décris-la avec autant de précision que si tu avais lu 200 de ses tweets. "
        "Ponctuation préférée, rapport aux emojis (rares ? signifiants ? jamais ?), "
        "tournures récurrentes, longueurs habituelles, casse, posture émotionnelle. "
        "Cette section sera relue mot pour mot par le copywriter — pas de phrase générique.\n\n"
        "**Vocabulaire** : invente des mots et expressions qu'elle/il dirait crédiblement, "
        "spécifiques à sa voix imaginée. Pas de mots fourre-tout (« amour », « relation ») — "
        "des marqueurs identitaires (genre les vocabulary_yes des autres personas : "
        "« système nerveux », « amour doux », « bare minimum », mais inventés pour CELLE-CI).\n\n"
        "**En plus de la persona, produis 3 tweets de preview** dans cette voix : un tweet "
        "isolé, un thread de 3 tweets, et un quote-trigger. Ces tweets servent à valider que la "
        "voix tient. Le thread doit nommer Compaatible en T2 ou T3 (jamais T1) — voir consignes "
        "système. Le quote-trigger doit poser une thèse incarnée clivante (cf. doctrine).\n\n"
        "Retourne UNIQUEMENT le JSON spécifié dans la consigne système."
    )

    return "\n".join(parts)


def generate_preview(
    gender: str,
    age: int,
    avatar_id_primary: int,
    avatar_id_secondary: int | None,
    first_name_hint: str | None,
    notes: str | None,
    model: str,
) -> dict[str, Any]:
    """Génère persona + 3 preview tweets en un appel LLM. Ne touche pas la DB.

    Retourne : {persona: {...}, previews: {isolated, thread, quote_trigger}, usage: {...}}
    Le thread est une liste de tweets (≥ 2).
    """
    avatar_primary = avatars_catalog.get_avatar(avatar_id_primary)
    if not avatar_primary:
        raise ValueError(f"Avatar {avatar_id_primary} inconnu (attendu 1-11).")
    avatar_secondary = avatars_catalog.get_avatar(avatar_id_secondary) if avatar_id_secondary else None
    if avatar_id_secondary and not avatar_secondary:
        raise ValueError(f"Avatar secondaire {avatar_id_secondary} inconnu.")
    if gender not in ("femme", "homme"):
        raise ValueError(f"gender doit être 'femme' ou 'homme', reçu : {gender!r}")
    if not isinstance(age, int) or age < 18 or age > 70:
        raise ValueError(f"age doit être un entier entre 18 et 70, reçu : {age!r}")

    user_message = _build_user_message(
        gender=gender,
        age=age,
        avatar_primary=avatar_primary,
        avatar_secondary=avatar_secondary,
        first_name_hint=first_name_hint,
        notes=notes,
    )

    result = llm_client.call_messages(
        model=model,
        system_blocks=prompts.build_system_for_manual_persona(),
        messages=[{"role": "user", "content": user_message}],
        max_tokens=8192,
        temperature=0.95,
    )

    try:
        parsed = parse_json_response(result["text"])
    except (json.JSONDecodeError, ValueError) as e:
        from brain.source_analyzer import _retry_json_repair
        repair = _retry_json_repair(
            model=model,
            system_blocks=prompts.build_system_for_manual_persona(),
            original_user_message=user_message,
            broken_response=result["text"],
            error=e,
        )
        parsed = parse_json_response(repair["text"])
        for k in result["usage"]:
            if k in repair["usage"] and isinstance(result["usage"][k], (int, float)):
                result["usage"][k] += repair["usage"][k]

    persona = parsed.get("persona") or {}
    previews = parsed.get("previews") or {}

    # Force les presets non négociables (sécurité au cas où le LLM les change)
    persona["gender"] = gender
    persona["age"] = age
    persona["avatar_id_primary"] = avatar_id_primary
    persona["avatar_id_secondary"] = avatar_id_secondary

    # Si l'utilisateur avait imposé un prénom, on l'écrase aussi
    if first_name_hint:
        persona["first_name"] = first_name_hint.strip()

    return {
        "persona": persona,
        "previews": {
            "isolated": (previews.get("isolated") or "").strip(),
            "thread": [t.strip() for t in (previews.get("thread") or []) if t and t.strip()],
            "quote_trigger": (previews.get("quote_trigger") or "").strip(),
        },
        "usage": result["usage"],
    }


def save_persona(persona: dict) -> int:
    """Insert la persona en DB. Retourne l'id.

    Logique de gestion d'unicité du prénom : réutilise celle de `persona_generator.insert_persona`.
    """
    from brain import persona_generator
    import psycopg2

    base_name = persona.get("first_name") or "Inconnue"

    def _try_insert(name: str) -> int | None:
        fields = {
            "first_name": name,
            "age": persona.get("age"),
            "gender": persona.get("gender") or "femme",
            "bio_twitter": persona.get("bio_twitter"),
            "backstory": persona.get("backstory") or "(créée manuellement, pas de backstory)",
            "avatar_id_primary": persona.get("avatar_id_primary"),
            "avatar_id_secondary": persona.get("avatar_id_secondary"),
            "voice_signature": persona.get("voice_signature"),
            "vocabulary_yes": persona.get("vocabulary_yes") or [],
            "vocabulary_no": persona.get("vocabulary_no") or [],
            "profile_photo_prompt": persona.get("profile_photo_prompt"),
            "banner_prompt": persona.get("banner_prompt"),
            "source_csv": None,
            "source_handle": None,
            "notes": persona.get("notes"),
        }
        cols = list(fields.keys())
        placeholders = ",".join(f"%({c})s" for c in cols)
        col_names = ",".join(cols)
        try:
            with db.cursor() as cur:
                cur.execute(
                    f"INSERT INTO mkt_personas_emerged ({col_names}) VALUES ({placeholders}) RETURNING id",
                    fields,
                )
                return cur.fetchone()["id"]
        except psycopg2.errors.UniqueViolation:
            return None

    pid = _try_insert(base_name)
    if pid is not None:
        return pid

    for suffix in range(2, 51):
        candidate = f"{base_name}-{suffix}"
        pid = _try_insert(candidate)
        if pid is not None:
            persona["first_name"] = candidate
            return pid

    raise RuntimeError(f"Impossible d'insérer la persona : 50 collisions sur {base_name}-N.")
