"""Stage 0 du pipeline : reverse-engineering du compte source.

Calcule les stats numériques (déterministes) + demande à l'IA d'extraire les mécanismes
qualitatifs (playbook).
"""
from __future__ import annotations
import json
import re
import sys
from typing import Any

from brain import csv_parser, prompts, llm_client


def analyze(parsed_csv: dict[str, Any], model: str) -> dict[str, Any]:
    """Reçoit le résultat de csv_parser.parse_csv() + un modèle Anthropic.
    Retourne {playbook: dict, stats: dict, usage: dict}.
    """
    rows = parsed_csv["rows"]
    content_col = parsed_csv["content_column"]

    # Stats déterministes
    stats = csv_parser.compute_engagement_stats(rows, content_col)
    stats["language_detected"] = parsed_csv["detected_language"]
    stats["handle"] = parsed_csv["source_handle"]

    # Échantillon adaptatif à envoyer à l'IA. Si l'user a limité à 50 tweets, on n'a pas
    # 90 tweets à envoyer. On dimensionne les buckets en proportion du pool dispo, plafonnés.
    n_rows = len(rows)
    if n_rows <= 50:
        # Petit pool : envoyer tout au top, pas de bottom/random (déjà inclus dans le top).
        top = rows
        bottom = []
        random_sample = []
    else:
        # Gros pool : top 50 + bottom 20 + random 20 (signal varié).
        top = csv_parser.top_n_by_engagement(rows, n=50)
        bottom = csv_parser.bottom_n_by_engagement(rows, n=20)
        random_sample = csv_parser.sample_random(rows, n=20)

    # Construire un dataset compact pour l'IA (tolérant aux colonnes désalignées)
    def shrink(row: dict) -> dict:
        return {
            "text": (row.get(content_col) or "").strip(),
            "likes": csv_parser.safe_int(row.get("likes", 0)),
            "retweets": csv_parser.safe_int(row.get("retweets", 0)),
            "views": csv_parser.safe_int(row.get("views", 0)),
            "engagement_rate": row.get("engagement_rate", ""),
        }

    sample = {
        "top_tweets_by_engagement": [shrink(r) for r in top],
        "low_engagement_tweets": [shrink(r) for r in bottom],
        "random_baseline_tweets": [shrink(r) for r in random_sample],
    }

    user_message = (
        f"Voici un échantillon du compte source `@{parsed_csv['source_handle'] or 'inconnu'}` "
        f"({parsed_csv['valid_rows']} tweets au total, langue dominante détectée : "
        f"`{parsed_csv['detected_language']}`).\n\n"
        f"Stats globales :\n```json\n{json.dumps(stats, indent=2, ensure_ascii=False)}\n```\n\n"
        f"Échantillon de 90 tweets (top 50 par engagement, bottom 20 vus mais peu engagés, "
        f"20 random pour baseline) :\n```json\n{json.dumps(sample, indent=2, ensure_ascii=False)}\n```\n\n"
        f"Produis le playbook au format JSON spécifié. Identifie 5 à 15 mécanismes. Sois précis et "
        f"opérationnel : un growth marketer doit pouvoir prendre ton playbook et reproduire le moteur."
    )

    result = llm_client.call_messages(
        model=model,
        system_blocks=prompts.build_system_for_analyze(),
        messages=[{"role": "user", "content": user_message}],
        max_tokens=8192,
        temperature=0.8,
    )

    # Parse avec self-repair via API en cas d'échec (analyze est 1-shot, on ne peut pas skip)
    try:
        playbook = parse_json_response(result["text"])
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[analyze] JSON invalide, retry self-fix · {e}", flush=True)
        repair = _retry_json_repair(
            model=model,
            system_blocks=prompts.build_system_for_analyze(),
            original_user_message=user_message,
            broken_response=result["text"],
            error=e,
        )
        playbook = parse_json_response(repair["text"])
        # Aggréger l'usage du retry
        for k in result["usage"]:
            if k in repair["usage"] and isinstance(result["usage"][k], (int, float)):
                result["usage"][k] += repair["usage"][k]

    return {
        "playbook": playbook,
        "stats": stats,
        "usage": result["usage"],
    }


def _retry_json_repair(
    model: str,
    system_blocks: list,
    original_user_message: str,
    broken_response: str,
    error: Exception,
) -> dict[str, Any]:
    """Demande à l'IA de réparer son propre JSON cassé. Un seul retry, temp basse."""
    fix_prompt = (
        "Ta réponse précédente contient du JSON invalide. "
        f"Erreur de parsing : {error}\n\n"
        "Renvoie UNIQUEMENT le JSON corrigé, exactement la même structure, "
        "rien d'autre — pas de commentaire avant ni après, pas de bloc markdown. "
        "Vérifie : guillemets correctement échappés à l'intérieur des strings, pas de "
        "virgules trailing, accolades/crochets équilibrés."
    )
    return llm_client.call_messages(
        model=model,
        system_blocks=system_blocks,
        messages=[
            {"role": "user", "content": original_user_message},
            {"role": "assistant", "content": broken_response},
            {"role": "user", "content": fix_prompt},
        ],
        max_tokens=8192,
        temperature=0.2,
    )


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse une réponse texte qui devrait contenir du JSON.

    Tolérant : strip des fences ```…```, recherche du bloc {...} le plus large,
    puis une cascade de réparations couvrant les cas d'échec observés en prod
    avec Gemini 3.1 pro (8192 max_tokens) :

    1. virgules trailing avant } ou ]
    2. guillemets typographiques “”‘’ remplacés par "'
    3. "Extra data" : du texte/objet en plus après le JSON racine → on garde
       uniquement le premier objet valide via raw_decode
    4. virgules manquantes entre deux items consécutifs d'un tableau
       (`}\\n  {` non précédé d'une virgule)
    5. JSON tronqué à max_tokens : reconstruire en gardant uniquement les
       items complets de tweets[] (ou mechanisms[]) et fermer proprement
    6. Rescue item-par-item : si un objet du tableau tweets[]/mechanisms[]
       est cassé (newline brut dans une string, quote non échappée, etc.), on
       parse les items un par un via raw_decode et on collecte ceux qui passent
       — au lieu de perdre les 20 d'un chunk.

    Toutes les tentatives utilisent strict=False pour tolérer les caractères de
    contrôle bruts (\\n, \\t) que le modèle laisse parfois dans les strings.

    Lève json.JSONDecodeError si rien ne marche (le caller peut alors retry).
    """
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()

    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in response (head: {text[:200]!r})")
    candidate = t[start : end + 1]

    # Tentative 1 : direct (strict=False : tolère \n bruts dans les strings)
    try:
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError:
        pass

    # Tentative 2 : retirer les virgules trailing avant } ou ]
    repaired = re.sub(r",(\s*[}\]])", r"\1", candidate)
    try:
        return json.loads(repaired, strict=False)
    except json.JSONDecodeError:
        pass

    # Tentative 3 : guillemets typographiques → droits.
    # Risqué : peut casser des strings qui contiennent légitimement ces caractères.
    aggressive = repaired
    for bad, good in [("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'")]:
        aggressive = aggressive.replace(bad, good)
    try:
        return json.loads(aggressive, strict=False)
    except json.JSONDecodeError:
        pass

    # Tentative 4 : "Extra data" — un objet/texte excédentaire après le JSON racine.
    # raw_decode parse juste le premier objet valide et ignore le reste.
    try:
        decoder = json.JSONDecoder(strict=False)
        obj, _consumed = decoder.raw_decode(aggressive.lstrip())
        return obj
    except json.JSONDecodeError:
        pass

    # Tentative 5 : virgules manquantes entre items consécutifs d'un tableau.
    # Pattern : `}` suivi de whitespace + `{` sans virgule entre les deux.
    # Pareil pour `]` suivi de `[` (rare). On ajoute la virgule manquante.
    repaired_commas = re.sub(r"(\}|\])\s*\n\s*(\{|\[)", r"\1,\n\2", aggressive)
    if repaired_commas != aggressive:
        try:
            return json.loads(repaired_commas, strict=False)
        except json.JSONDecodeError:
            pass
        # Et avec raw_decode au cas où il reste de l'extra data
        try:
            decoder = json.JSONDecoder(strict=False)
            obj, _consumed = decoder.raw_decode(repaired_commas.lstrip())
            return obj
        except json.JSONDecodeError:
            pass

    # Tentative 6 (anciennement "tronqué") : JSON tronqué à max_tokens. Le modèle
    # a été coupé en plein tweet/mécanisme. On retrouve le dernier objet complet
    # dans le tableau principal (tweets[] ou mechanisms[]) et on ferme proprement.
    truncated = _try_recover_truncated_array(repaired_commas)
    if truncated is not None:
        try:
            return json.loads(truncated, strict=False)
        except json.JSONDecodeError:
            pass

    # Tentative 7 : rescue item-par-item. Un seul item cassé (newline brut, quote
    # mal échappée, "Extra data" interne, virgule manquante locale, etc.) ne doit
    # pas tuer les 19 autres d'un chunk. On parcourt tweets[]/mechanisms[] avec
    # raw_decode, on collecte les objets qui parsent, on skip ceux qui plantent.
    rescued = _rescue_array_item_by_item(repaired_commas)
    if rescued is not None:
        return rescued

    # Échec final : log la région autour de e.pos (pas un range fixe arbitraire)
    try:
        json.loads(candidate, strict=False)
    except json.JSONDecodeError as e:
        lo = max(0, e.pos - 250)
        hi = min(len(candidate), e.pos + 250)
        print(
            f"[parse_json] echec final · {e} · candidate[{lo}:{hi}]={candidate[lo:hi]!r}",
            file=sys.stderr,
            flush=True,
        )
        raise


def _try_recover_truncated_array(text: str) -> str | None:
    """Tente de récupérer un JSON tronqué par max_tokens.

    Stratégie : repérer un tableau principal de la forme `"key": [ { ... }, { ... }, { incomplet`,
    couper après le dernier objet COMPLET du tableau (matching `}` au bon niveau),
    fermer le tableau et l'objet racine.

    Cibles connues : `"tweets": [...]`, `"mechanisms": [...]`.
    Retourne None si la structure n'est pas reconnaissable.
    """
    for key in ("tweets", "mechanisms"):
        marker = f'"{key}"'
        i_key = text.find(marker)
        if i_key < 0:
            continue
        # Trouver le `[` qui suit la clé
        i_bracket = text.find("[", i_key)
        if i_bracket < 0:
            continue

        # Parcourir le tableau, tracker la profondeur des `{}` et la position du
        # dernier `}` qui ferme un objet de niveau immédiat dans le tableau (depth=1
        # juste avant fermeture, donc on cherche la transition 1→0 sur les accolades).
        depth_brace = 0
        in_string = False
        escape = False
        last_complete_obj_end = -1
        for j in range(i_bracket + 1, len(text)):
            ch = text[j]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth_brace += 1
            elif ch == "}":
                depth_brace -= 1
                if depth_brace == 0:
                    last_complete_obj_end = j  # inclus
            elif ch == "]" and depth_brace == 0:
                # tableau fermé naturellement : pas tronqué, on laisse json.loads gérer
                return None

        if last_complete_obj_end < 0:
            continue

        # Reconstruction : on garde tout jusqu'au dernier `}` complet, on ferme
        # le tableau et l'objet racine. On retire les éventuelles virgules trailing.
        rebuilt = text[: last_complete_obj_end + 1].rstrip()
        rebuilt = re.sub(r",\s*$", "", rebuilt)
        rebuilt += "]}"
        return rebuilt

    return None


def _rescue_array_item_by_item(text: str) -> dict[str, Any] | None:
    """Parse les items du tableau principal un par un avec raw_decode.

    Quand un seul objet de tweets[] (ou mechanisms[]) est cassé — newline brut
    dans une string, quote interne non échappée, "Extra data" interne, virgule
    manquante locale — `json.loads()` rejette tout le document. Ce rescue scanne
    les items en sautant les cassés, ce qui sauve 19 tweets sur 20 au lieu de 0.

    Retourne `{key: [items_OK]}` ou None si :
    - aucun marqueur "tweets"/"mechanisms" trouvé
    - aucun item n'a pu être parsé
    """
    for key in ("tweets", "mechanisms"):
        i_key = text.find(f'"{key}"')
        if i_key < 0:
            continue
        i_bracket = text.find("[", i_key)
        if i_bracket < 0:
            continue

        items: list[dict] = []
        skipped = 0
        decoder = json.JSONDecoder(strict=False)
        idx = i_bracket + 1
        n = len(text)

        while idx < n:
            # Skip whitespace/virgules entre items
            while idx < n and text[idx] in " \t\n\r,":
                idx += 1
            if idx >= n:
                break
            if text[idx] == "]":
                break
            if text[idx] != "{":
                # Structure non reconnue, on s'arrête
                break

            try:
                obj, end = decoder.raw_decode(text, idx)
                if isinstance(obj, dict):
                    items.append(obj)
                idx = end
            except json.JSONDecodeError:
                skipped += 1
                # Avancer au prochain `{` qui ressemble à un nouvel item.
                # Pattern : virgule (séparateur d'items dans un array JSON),
                # éventuellement suivie de whitespace, puis `{`. On EXIGE la
                # virgule pour éviter de matcher un objet imbriqué interne
                # (ex. `"meta": {...}` qui a un `: {` que `\s\{` capturerait
                # à tort, conduisant à parser le sous-objet comme un faux item).
                m = re.search(r",\s*\{", text[idx + 1 :])
                if not m:
                    break
                # m.end() est la position APRÈS le match dans le slice,
                # donc m.end() - 1 = position du `{`. Absolu = idx + 1 + ...
                idx = idx + 1 + m.end() - 1

        if items:
            if skipped:
                print(
                    f"[parse_json] rescue item-by-item · {len(items)} items recuperes, {skipped} skipped",
                    file=sys.stderr,
                    flush=True,
                )
            return {key: items}

    return None
