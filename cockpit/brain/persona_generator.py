"""Stage 1 : génération d'une persona Compaatible féminine UNIQUE.

La persona n'est PAS créée à partir du playbook abstrait seul : elle voit les tweets
sources eux-mêmes (top engagement + échantillon aléatoire) pour décider qui elle est.
Ce sont les tweets qui déterminent l'histoire, le nom et la bio (règle Loys).
"""
from __future__ import annotations
import json
from typing import Any

from brain import prompts, llm_client, db, csv_parser


# Quantité de tweets sources à donner à voir à la persona.
# Top 30 par engagement + 10 random = vision représentative sans saturer les tokens.
PERSONA_TOP_SAMPLE = 30
PERSONA_RANDOM_SAMPLE = 10


def get_existing_personas() -> list[dict]:
    """Liste les personas déjà créées (prénom + avatar) pour éviter les doublons."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, first_name, avatar_id_primary, bio_twitter "
            "FROM mkt_personas_emerged ORDER BY id"
        )
        return [dict(r) for r in cur.fetchall()]


def _build_tweets_sample(parsed_csv: dict) -> list[str]:
    """Construit l'échantillon de tweets sources que la persona va lire pour décider qui elle est."""
    rows = parsed_csv["rows"]
    content_col = parsed_csv["content_column"]

    top = csv_parser.top_n_by_engagement(rows, n=PERSONA_TOP_SAMPLE)
    random_sample = csv_parser.sample_random(rows, n=PERSONA_RANDOM_SAMPLE)

    seen: set[str] = set()
    texts: list[str] = []
    for r in top + random_sample:
        t = (r.get(content_col) or "").strip()
        if t and t not in seen:
            seen.add(t)
            texts.append(t)
    return texts


def generate(
    playbook: dict,
    model: str,
    parsed_csv: dict,
    source_csv: str = None,
    source_handle: str = None,
) -> dict[str, Any]:
    """Génère une persona unique. Retourne {persona: dict_to_insert, persona_id: int, usage: dict}."""
    existing = get_existing_personas()
    existing_names = [p["first_name"] for p in existing]
    existing_summary = (
        "\n".join(f"- {p['first_name']} (avatar {p['avatar_id_primary']}): {p['bio_twitter'] or ''}" for p in existing)
        or "Aucune persona existante (c'est la première)."
    )

    tweets_sample = _build_tweets_sample(parsed_csv)
    tweets_block = "\n".join(f"- {t}" for t in tweets_sample) or "(aucun tweet exploitable)"

    user_message = (
        "## TWEETS SOURCES (échantillon représentatif)\n\n"
        "Voici un échantillon des vrais tweets du compte source (top engagement + échantillon "
        "aléatoire). **Ce sont eux qui déterminent qui est la persona.** Lis-les attentivement, "
        "imprègne-toi de la voix, du grain de personnalité, des préoccupations, du rythme, du "
        "vocabulaire, des références. La persona doit être celle qui aurait pu écrire ces tweets.\n\n"
        f"{tweets_block}\n\n"
        "## PLAYBOOK (synthèse des mécanismes)\n\n"
        f"```json\n{json.dumps(playbook, indent=2, ensure_ascii=False)}\n```\n\n"
        "## PERSONAS DÉJÀ CRÉÉES (à NE PAS dupliquer ni copier)\n\n"
        f"{existing_summary}\n\n"
        f"Prénoms déjà utilisés (ne réutilise AUCUN) : {existing_names or 'aucun'}.\n\n"
        "## TA MISSION\n\n"
        "Crée une persona féminine totalement nouvelle, qui aurait crédiblement pu écrire les "
        "tweets ci-dessus, branchée sur le monde Compaatible avec un avatar (1-11) qui résonne "
        "avec les douleurs et préoccupations exprimées dans les tweets. "
        "Son histoire (backstory), son prénom, sa bio doivent **émerger des tweets**, pas être "
        "plaqués génériquement. Retourne UNIQUEMENT le JSON spécifié."
    )

    result = llm_client.call_messages(
        model=model,
        system_blocks=prompts.build_system_for_persona(),
        messages=[{"role": "user", "content": user_message}],
        max_tokens=2048,
        temperature=0.95,
    )

    from brain.source_analyzer import parse_json_response, _retry_json_repair

    try:
        persona = parse_json_response(result["text"])
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[persona] JSON invalide, retry self-fix · {e}", flush=True)
        repair = _retry_json_repair(
            model=model,
            system_blocks=prompts.build_system_for_persona(),
            original_user_message=user_message,
            broken_response=result["text"],
            error=e,
        )
        persona = parse_json_response(repair["text"])
        for k in result["usage"]:
            if k in repair["usage"] and isinstance(result["usage"][k], (int, float)):
                result["usage"][k] += repair["usage"][k]

    # Vérification d'unicité du prénom. Stratégie : retry IA une fois, puis suffix garanti unique.
    name = (persona.get("first_name") or "Inconnue").strip() or "Inconnue"
    if name in existing_names:
        retry_msg = (
            f"Le prénom `{name}` est déjà utilisé. Génère une NOUVELLE persona avec un autre prénom. "
            "Les autres champs peuvent rester proches si pertinent mais DIFFÉRENTS dans l'histoire."
        )
        retry_result = llm_client.call_messages(
            model=model,
            system_blocks=prompts.build_system_for_persona(),
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": result["text"]},
                {"role": "user", "content": retry_msg},
            ],
            max_tokens=2048,
            temperature=1.0,
        )
        persona = parse_json_response(retry_result["text"])
        # Aggrege usage
        for k in result["usage"]:
            result["usage"][k] += retry_result["usage"].get(k, 0) if isinstance(result["usage"][k], (int, float)) else 0

        name = (persona.get("first_name") or name).strip() or name

    # Filet de sécurité : si le retry IA renvoie aussi un doublon (ou si l'IA ignore la consigne),
    # on append un suffixe numérique pour garantir l'unicité côté DB (contrainte UNIQUE).
    if name in existing_names:
        suffix = 2
        while f"{name}-{suffix}" in existing_names and suffix < 100:
            suffix += 1
        name = f"{name}-{suffix}"
        persona["first_name"] = name

    # Insertion en DB
    persona_id = insert_persona(persona, source_csv=source_csv, source_handle=source_handle)

    return {
        "persona": persona,
        "persona_id": persona_id,
        "usage": result["usage"],
    }


def insert_persona(persona: dict, source_csv: str = None, source_handle: str = None) -> int:
    """Insère la persona en DB. Retourne l'id.

    Concurrence : entre `get_existing_personas()` et cet INSERT, un autre run en parallèle
    peut avoir inséré une persona avec le même first_name. On retombe sur la contrainte
    UNIQUE. Filet de sécurité : on retry jusqu'à 50 fois en appendant un suffixe numérique.
    """
    import psycopg2

    base_name = persona["first_name"]

    def _try_insert(name: str) -> int | None:
        fields = {
            "first_name": name,
            "age": persona.get("age"),
            "bio_twitter": persona.get("bio_twitter"),
            "backstory": persona.get("backstory"),
            "avatar_id_primary": persona.get("avatar_id_primary"),
            "avatar_id_secondary": persona.get("avatar_id_secondary"),
            "voice_signature": persona.get("voice_signature"),
            "vocabulary_yes": persona.get("vocabulary_yes") or [],
            "vocabulary_no": persona.get("vocabulary_no") or [],
            "profile_photo_prompt": persona.get("profile_photo_prompt"),
            "banner_prompt": persona.get("banner_prompt"),
            "source_csv": source_csv,
            "source_handle": source_handle,
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

    # Collision race : append un suffixe et retry
    for suffix in range(2, 51):
        candidate = f"{base_name}-{suffix}"
        pid = _try_insert(candidate)
        if pid is not None:
            persona["first_name"] = candidate  # reflète le nom final pour le caller
            return pid

    raise RuntimeError(
        f"Impossible d'insérer la persona : 50 collisions UNIQUE sur {base_name}-N. "
        "DB probablement saturée de personas portant ce prénom."
    )
