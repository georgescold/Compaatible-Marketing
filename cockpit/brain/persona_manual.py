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


# Niveaux d'intensité émotionnelle proposés à l'utilisateur côté UI.
# Le LLM reçoit une calibration dédiée selon le niveau choisi (cf. _emotional_intensity_spec).
EMOTIONAL_INTENSITY_LEVELS = [
    ("tres_emotionnel", "Très émotionnel·le"),
    ("emotionnel",      "Émotionnel·le"),
    ("peu_emotionnel",  "Peu émotionnel·le"),
    ("rationnel",       "Rationnel·le"),
]
EMOTIONAL_INTENSITY_DEFAULT = "tres_emotionnel"


def _emotional_intensity_spec(level: str) -> str:
    """Retourne la section de calibration émotionnelle à insérer dans le user_message.

    Décrit le niveau choisi en PRINCIPES (pas de citations littérales d'emojis ou de
    phrases, conformément à la doctrine anti-hardcoded). Le LLM doit matérialiser
    ces principes dans le voice_signature ET dans les 3 preview tweets.
    """
    if level == "tres_emotionnel":
        body = (
            "**TRÈS ÉMOTIONNEL·LE — abus assumé, théâtralité maximale, mais JAMAIS "
            "mécanique.**\n\n"
            "**Principe fondateur** : la voix est dans l'excès. Les emojis débordent, "
            "la ponctuation explose, les capitales surgissent, l'amplification est "
            "constante. **Le seul interdit, c'est la prévisibilité structurelle** — "
            "l'abus doit varier tweet-à-tweet en quantité, en position, en registre. "
            "Une drama queen authentique n'écrit jamais deux tweets pareils ; elle "
            "réinvente son intensité à chaque fois.\n\n"
            "**TA MISSION : inventer LE RYTHME PROPRE À CETTE PERSONA, pas appliquer "
            "un gabarit générique.** À partir de la fiche avatar (psychologie, peurs, "
            "ce qui la fait réagir, sa direction créative), de ses notes utilisateur, "
            "de son métier et de son contexte de vie, déduis :\n"
            "- **Sa propre dynamique d'emojis** : à quelle fréquence elle en met, "
            "comment elle les distribue, lesquels reviennent le plus, où elle les "
            "place préférentiellement, quand elle s'en abstient totalement. Une "
            "persona Avatar 2 hyperconnectée n'utilise pas les mêmes emojis qu'une "
            "Avatar 6 idéaliste romantique, ni à la même cadence, ni dans les mêmes "
            "contextes.\n"
            "- **Sa propre signature de ponctuation démultipliée** : préfère-t-elle "
            "les `??` ou les `!!` ? Combien de fois max les répète-t-elle ? "
            "Utilise-t-elle des mélanges atypiques (`?!?!`, `!??`, `...!`) ? Quels "
            "sont ses tics ponctuationnels uniques ?\n"
            "- **Son rapport aux capitales** : un mot seul ? Une phrase entière ? "
            "Dans quels contextes les déclenche-t-elle ?\n\n"
            "**Décris EXPLICITEMENT cette dynamique dans `voice_signature`** — c'est "
            "ce qui rendra chaque persona « très émotionnel·le » singulière au lieu "
            "d'avoir 5 personas qui font la même chose.\n\n"
            "### Garde-fous de variété (impératifs, peu importe la dynamique inventée)\n\n"
            "Quelle que soit la dynamique que tu inventes pour cette persona, ces "
            "principes structurels doivent toujours s'appliquer :\n\n"
            "- **Abondance générale** : le registre est l'abus, pas la modération. "
            "La majorité des tweets doit porter au moins UN marqueur visuel fort "
            "(emoji, ponctuation démultipliée, capslock, ou plusieurs). Le silence "
            "visuel total reste rare — réservé aux pics de lucidité tranchante ou de "
            "rage froide.\n"
            "- **Variabilité tweet-à-tweet** : aucun tweet ne doit ressembler "
            "structurellement au précédent côté emojis ET ponctuation. Le nombre, la "
            "position et le registre doivent varier d'un tweet à l'autre, sans "
            "pattern prévisible.\n"
            "- **Variété de placement des emojis** : alterne fin de tweet, milieu "
            "(entre deux phrases), début (comme un cri visuel d'ouverture), entre "
            "deux mots (pour souligner un concept). Pas 8 tweets de suite avec "
            "emojis uniquement en fin.\n"
            "- **Variété de famille d'emojis** : selon le tweet, mélange émojis "
            "émotifs (visages expressifs), symboliques (cœurs, feu, éclair, larmes), "
            "naturels (lune, fleurs, météo), gestuels (mains, applaudissements), ou "
            "thématiques (selon l'univers de la persona). La persona peut avoir un "
            "ou deux emojis-signatures qui reviennent plus souvent, mais pas dans "
            "chaque tweet — ils gardent leur poids parce qu'ils sont sélectifs.\n"
            "- **Test rapide impératif** : si en regardant les 5 derniers tweets de "
            "cette persona on peut PRÉDIRE combien d'emojis aura le 6e et où ils "
            "seront placés, c'est un pattern robotique → casse-le. La surprise "
            "structurelle est la marque du naturel.\n\n"
            "### Autres dimensions du registre très émotionnel\n\n"
            "- **Formules d'amplification omniprésentes** : adverbes intensifs en "
            "veux-tu en voilà, hyperboles assumées, métaphores dramatiques, prise à "
            "témoin du lecteur. Invente les marqueurs d'amplification propres à "
            "CETTE persona (pas de formules à citer littéralement — décris des "
            "patterns).\n"
            "- **Théâtralité maximale assumée** : exagération consciente des chiffres "
            "et des situations, dramatisation d'événements banals, ton de quelqu'un "
            "qui RACONTE à voix haute en gesticulant à ses copines à 2h du matin. "
            "La voix EST grande forme, c'est sa fréquence.\n"
            "- **Garde-fou** : malgré l'extravagance débordante, la voix reste capable "
            "de tranchant et de lucidité. L'émotion n'est pas creuse — elle est la "
            "matière première d'observations vraies. Une drama queen LUCIDE."
        )
    elif level == "emotionnel":
        body = (
            "**ÉMOTIONNEL·LE — chaleureuse, présente, modérée.**\n\n"
            "**Principe** : émotion présente sans débordement. La voix incarne la "
            "chaleur et la sensibilité, mais sans hyperbole ni théâtralité. Les "
            "marqueurs visuels (ponctuation expressive, emojis, capitales) existent "
            "ponctuellement, jamais en saturation.\n\n"
            "**TA MISSION : inventer le rythme propre à CETTE persona** à partir "
            "de la fiche avatar (psychologie, peurs, direction créative), des notes "
            "utilisateur, du métier et du contexte de vie. Déduis :\n"
            "- À quelle fréquence cette persona précise utilise des emojis (rare ? "
            "ponctuelle ? régulière mais sobre ?), lesquels reviennent, dans quels "
            "contextes.\n"
            "- Sa ponctuation expressive favorite : double interrogation "
            "occasionnelle ? Exclamations rares ? Points de suspension ? Tirets ?\n"
            "- Son rapport aux capitales (rare ou occasionnel sur un mot).\n\n"
            "**Décris EXPLICITEMENT cette dynamique dans `voice_signature`** — sans "
            "elle, deux personas « émotionnel·le » seraient interchangeables.\n\n"
            "### Garde-fous de variété (impératifs)\n\n"
            "- **Sobriété dominante** : la majorité des tweets passent par les mots, "
            "pas par les marqueurs visuels. Un emoji bien placé vaut mieux que trois "
            "qui diluent.\n"
            "- **Variabilité tweet-à-tweet** : aucun pattern mécanique « toujours "
            "1 emoji à la fin », « toujours `??` ici ». Le placement, la quantité, "
            "et la présence/absence varient sans prévisibilité.\n"
            "- **Quand emoji il y a** : 1 le plus souvent, 2 quand l'émotion le "
            "justifie, exceptionnellement 3 pour un pic. Au-delà → tu es passé en "
            "mode « très émotionnel », recule.\n"
            "- **Placement varié** : majorité en fin de tweet certes, mais glisse "
            "parfois un emoji au milieu d'une phrase pour ponctuer un mot. Pas un "
            "automatisme.\n"
            "- **Test rapide** : si chaque tweet finit pareil (même position, même "
            "nombre d'emojis), c'est raté. La variété structurelle est non négociable.\n\n"
            "- **Émotion incarnée mais maîtrisée** : la chaleur se ressent dans le "
            "choix des mots, pas dans une accumulation de marqueurs visuels.\n"
            "- **Voix** : sensible et engagée, sans hyperbole."
        )
    elif level == "peu_emotionnel":
        body = (
            "**PEU ÉMOTIONNEL·LE — retenue, contrôle, pudeur.**\n"
            "- **Ponctuation classique et sobre** : point final standard, virgules "
            "canoniques, jamais de répétitions de signes. Pas de double point "
            "d'interrogation.\n"
            "- **Capitales très rares** : uniquement pour vrai pic d'emphase, et "
            "même alors c'est une exception.\n"
            "- **Emojis rares ou absents** : si présents, exceptionnels (un seul, "
            "sobre, en bout de tweet, et pas dans la majorité des tweets).\n"
            "- **Émotion exprimée par le CONTENU, pas par la forme** : la voix "
            "laisse l'émotion émerger par ce qu'elle dit, jamais par comment elle "
            "le décore.\n"
            "- **Phrases posées et contrôlées** : la voix donne l'impression de "
            "quelqu'un qui pèse ses mots, qui dit moins pour dire mieux.\n"
            "- **Voix** : retenue, élégance, pudeur — l'émotion se devine."
        )
    elif level == "rationnel":
        body = (
            "**RATIONNEL·LE — analytique, mesurée, froide.**\n"
            "- **Ponctuation strictement classique** : zéro répétition de signe, "
            "zéro point de suspension allongé, ponctuation grammaticalement correcte "
            "et neutre.\n"
            "- **Aucune capitale d'emphase** : la voix ne crie jamais visuellement.\n"
            "- **Zéro emoji** (ou un seul, exceptionnel, dans très peu de tweets — "
            "et même alors c'est presque une anomalie).\n"
            "- **Langage analytique et démonstratif** : observations rigoureuses, "
            "raisonnements posés, distance face au sujet.\n"
            "- **Émotion uniquement implicite** : jamais affichée, jamais nommée "
            "directement. Si la persona ressent quelque chose, ça transparaît "
            "uniquement par la précision de l'observation.\n"
            "- **Voix** : lucidité froide, registre proche de l'essai court — la "
            "persona pourrait écrire dans une revue intellectuelle sans changer de "
            "ton."
        )
    else:
        # Fallback : émotionnel modéré
        body = _emotional_intensity_spec("emotionnel")[len("## CALIBRATION ÉMOTIONNELLE OBLIGATOIRE\n\n"):]

    return (
        "## CALIBRATION ÉMOTIONNELLE OBLIGATOIRE\n\n"
        "L'utilisateur a choisi un niveau d'intensité émotionnelle précis pour cette "
        "persona. Tu DOIS matérialiser ce niveau dans :\n"
        "1. Le champ `voice_signature` (la description des patterns d'écriture).\n"
        "2. Le champ `vocabulary_yes` (la palette lexicale cohérente avec ce niveau).\n"
        "3. Les 3 preview tweets (isolated, thread, quote_trigger) — ils doivent "
        "incarner ce niveau de façon évidente.\n\n"
        f"{body}\n\n"
        "**Ce niveau prime sur les défauts génériques** : même si l'avatar choisi est "
        "habituellement écrit dans un registre différent, c'est ce niveau émotionnel "
        "que tu appliques. C'est un choix éditorial explicite de l'utilisateur."
    )


def _build_user_message(
    gender: str,
    age: int,
    avatar_primary: dict,
    avatar_secondary: dict | None,
    first_name_hint: str | None,
    notes: str | None,
    emotional_intensity: str = EMOTIONAL_INTENSITY_DEFAULT,
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

    # Niveau d'intensité émotionnelle (calibration explicite de l'écriture).
    level_label = dict(EMOTIONAL_INTENSITY_LEVELS).get(emotional_intensity, emotional_intensity)
    parts.append(f"- **Intensité émotionnelle** : {level_label}")

    if notes:
        parts.append(f"\n**Notes additionnelles de l'utilisateur** :\n{notes}")

    # Section dédiée qui décrit le niveau en principes opératoires.
    parts.append("\n" + _emotional_intensity_spec(emotional_intensity))

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
    emotional_intensity: str = EMOTIONAL_INTENSITY_DEFAULT,
) -> dict[str, Any]:
    """Génère persona + 3 preview tweets en un appel LLM. Ne touche pas la DB.

    Retourne : {persona: {...}, previews: {isolated, thread, quote_trigger}, usage: {...}}
    Le thread est une liste de tweets (≥ 2).

    `emotional_intensity` : niveau de calibration émotionnelle de l'écriture
    ('tres_emotionnel' | 'emotionnel' | 'peu_emotionnel' | 'rationnel'). Influence
    voice_signature, vocabulary_yes et les 3 preview tweets. Cf. EMOTIONAL_INTENSITY_LEVELS.
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
    valid_levels = {k for k, _ in EMOTIONAL_INTENSITY_LEVELS}
    if emotional_intensity not in valid_levels:
        emotional_intensity = EMOTIONAL_INTENSITY_DEFAULT

    user_message = _build_user_message(
        gender=gender,
        age=age,
        avatar_primary=avatar_primary,
        avatar_secondary=avatar_secondary,
        first_name_hint=first_name_hint,
        notes=notes,
        emotional_intensity=emotional_intensity,
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


VISUAL_KINDS = ("profile_photo", "banner")


def regenerate_visual_prompt(persona: dict, kind: str, model: str) -> dict[str, Any]:
    """Régénère UNIQUEMENT le prompt visuel demandé (photo_de_profil OU bannière)
    pour une persona existante. Fait un appel LLM ciblé qui ne touche pas aux
    autres champs (voix, backstory, etc.).

    `persona` : dict complet de la persona (au moins first_name, age, gender,
        avatar_id_primary, bio_twitter, backstory, voice_signature, vocabulary_yes,
        vocabulary_no). L'avatar primaire est chargé depuis le catalogue.
    `kind` : 'profile_photo' ou 'banner'.
    `model` : id du modèle LLM.

    Retourne : {prompt: str (JSON string en anglais, comme le format des specs),
                usage: {input_tokens, cached_tokens, output_tokens, cost_usd_estimate}}
    """
    if kind not in VISUAL_KINDS:
        raise ValueError(f"kind doit être 'profile_photo' ou 'banner', reçu : {kind!r}")

    avatar_primary = avatars_catalog.get_avatar(persona.get("avatar_id_primary"))
    if not avatar_primary:
        raise ValueError(f"Avatar {persona.get('avatar_id_primary')} inconnu pour cette persona.")

    # Bloc utilisateur : on transmet le contexte persona qui sert à dériver le visuel,
    # puis on précise quelle section régénérer.
    persona_block = {
        "first_name": persona.get("first_name"),
        "age": persona.get("age"),
        "gender": persona.get("gender"),
        "bio_twitter": persona.get("bio_twitter"),
        "backstory": persona.get("backstory"),
        "voice_signature": persona.get("voice_signature"),
        "vocabulary_yes": persona.get("vocabulary_yes") or [],
        "vocabulary_no": persona.get("vocabulary_no") or [],
        "avatar_id_primary": persona.get("avatar_id_primary"),
        "avatar_id_secondary": persona.get("avatar_id_secondary"),
        # Le prompt actuel sert au LLM pour produire QUELQUE CHOSE DE DIFFÉRENT
        # (anti-répétition implicite — on lui montre le précédent).
        "current_prompt_to_replace": (
            persona.get("profile_photo_prompt") if kind == "profile_photo"
            else persona.get("banner_prompt")
        ),
    }

    user_message = (
        f"## CONTEXTE PERSONA EXISTANTE\n\n"
        f"```json\n{json.dumps(persona_block, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## FICHE COMPLÈTE DE L'AVATAR PRIMAIRE\n\n"
        f"{avatar_primary['full_block']}\n\n"
        f"## MISSION\n\n"
        + (
            "Génère UN NOUVEAU `profile_photo_prompt` pour cette persona, en respectant "
            "intégralement la SECTION DÉDIÉE LE CHAMP `profile_photo_prompt` du prompt "
            "système. **Ne touche à aucun autre champ** de la persona. **Différencie-toi "
            "du `current_prompt_to_replace`** ci-dessus : varie la scène, l'activité, "
            "l'éclairage, l'angle — produis quelque chose de différent qui reste fidèle à "
            "la persona. Retourne UNIQUEMENT le JSON spécifié ci-dessous (rien avant, "
            "rien après).\n\n"
            "## FORMAT DE SORTIE\n\n"
            "```json\n"
            "{\n"
            '  \"profile_photo_prompt\": \"<string contenant un objet JSON encodé en anglais '
            'respectant le format de la SECTION DÉDIÉE profile_photo_prompt (champs : scene, '
            'subject_position, gaze, physical_traits, clothing, framing, lighting, decor, '
            'style, negative_prompt, full_prompt). Le full_prompt doit ouvrir par une '
            'formule snapshot casual + beauté naturelle (cf. spec).>\"\n'
            "}\n"
            "```\n"
            if kind == "profile_photo" else
            "Génère UN NOUVEAU `banner_prompt` pour cette persona, en respectant "
            "intégralement la SECTION DÉDIÉE LE CHAMP `banner_prompt` du prompt système "
            "(bannière = choix personnel délibéré de la persona, reflet de ses centres "
            "d'intérêt / valeurs / esthétique). **Ne touche à aucun autre champ** de la "
            "persona. **Différencie-toi du `current_prompt_to_replace`** ci-dessus : "
            "propose un autre angle, un autre sujet, une autre composition. Retourne "
            "UNIQUEMENT le JSON spécifié ci-dessous (rien avant, rien après).\n\n"
            "## FORMAT DE SORTIE\n\n"
            "```json\n"
            "{\n"
            '  \"banner_prompt\": \"<string contenant un objet JSON encodé en anglais '
            'respectant le format de la SECTION DÉDIÉE banner_prompt (champs : '
            'persona_expression, subject, medium, palette, composition, lighting, '
            'emotional_charge, identity_coherence_with_profile, negative_prompt, '
            'full_prompt). Le full_prompt doit ouvrir par une formule du type \\\"A '
            'Twitter/X header banner that [persona descriptor] would choose for herself, '
            'showing...\\\" et inclure ratio 3:1 et 1500x500.>\"\n'
            "}\n"
            "```\n"
        )
    )

    result = llm_client.call_messages(
        model=model,
        system_blocks=prompts.build_system_for_manual_persona(),
        messages=[{"role": "user", "content": user_message}],
        max_tokens=4096,
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

    field_name = "profile_photo_prompt" if kind == "profile_photo" else "banner_prompt"
    new_prompt = (parsed.get(field_name) or "").strip()
    if not new_prompt:
        raise RuntimeError(f"Le LLM n'a pas renvoyé de {field_name} exploitable.")

    return {"prompt": new_prompt, "usage": result["usage"]}


def update_persona_visual(persona_id: int, kind: str, new_prompt: str) -> None:
    """Met à jour UNIQUEMENT le prompt visuel (profile_photo_prompt OU banner_prompt)
    de la persona en DB. Ne touche pas aux autres champs.
    """
    if kind not in VISUAL_KINDS:
        raise ValueError(f"kind doit être 'profile_photo' ou 'banner', reçu : {kind!r}")
    field = "profile_photo_prompt" if kind == "profile_photo" else "banner_prompt"
    with db.cursor() as cur:
        cur.execute(
            f"UPDATE mkt_personas_emerged SET {field} = %s WHERE id = %s",
            (new_prompt, persona_id),
        )


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
