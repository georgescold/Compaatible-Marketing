"""Insertion d'un batch test de 8 images déjà analysées visuellement.

Sert à valider :
- Schéma DB (insertion de tous les champs)
- Format des métadonnées
- Pipeline insert_image()

Ces 8 images ont été observées dans la session du 2026-05-15 pour comprendre la niche.
"""
from insert_image import insert_image


SAMPLES = [
    {
        "filename": "3f8809607c3795f10c44525fbee2098d.jpg",
        "image_type": "anime_illustration",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Illustration style anime/Ghibli d'un jeune couple assis sur la véranda en bois "
            "d'un cottage au coucher du soleil. Le garçon, cheveux noirs courts en t-shirt vert, "
            "joue de la guitare acoustique. La fille, longue chevelure brune en robe blanche, "
            "appuie sa tête contre son épaule en jouant elle aussi. Guirlande de petites lumières "
            "warm-white accrochées à la pergola. Vallée brumeuse et montagnes violettes à l'horizon. "
            "Petites lucioles dans l'herbe en premier plan. Atmosphère extrêmement cozy, intime, "
            "slice-of-life. Lumière dorée crépusculaire."
        ),
        "marketing_use": (
            "Image idéale pour illustrer la promesse d'une rencontre profonde et durable. "
            "À utiliser pour les avatars 6 (Idéaliste Rêveur) en tweets poétiques type 'silence à deux', "
            "et 7 (Jeune Mature) pour évoquer l'amour calme qu'il/elle cherche. Aussi avatar 9 "
            "(Fraîchement Séparé) pour visualiser ce que pourrait être la prochaine étape."
        ),
        "emotions": ["intimacy", "warmth", "calm", "peace", "wonder", "softness"],
        "ambiance": ["cozy", "dreamy", "sunset", "golden_hour", "cinematic"],
        "setting": ["outdoor", "porch", "countryside", "mountain_view"],
        "colors": ["warm", "muted", "amber", "violet"],
        "style_tags": ["anime_illustration", "studio_ghibli_vibe", "slice_of_life"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "mid_shot",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 7, 9, 5],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format vertical 1031x1299. Illustration générée probablement par IA (Ghibli style). Pas de droits photographiques sur des personnes réelles donc utilisation libre.",
    },
    {
        "filename": "0948d30bd48a8008f4f87974db9b7696.jpg",
        "image_type": "photo_real",
        "subject_type": "body_part",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo serrée des mains d'un couple lors d'un mariage indo-pakistanais. Main de la mariée "
            "couverte de motifs henné élaborés en orange-rouge, portant des bagues dorées et un "
            "bracelet de roses pastel. Main du marié, simple, avec un anneau d'or. Au second plan, "
            "robe traditionnelle bleu pastel brodée d'argent. Vue depuis derrière les mains, "
            "intime et symbolique. Symbole de l'engagement mutuel."
        ),
        "marketing_use": (
            "Image très belle mais spécifiquement culturelle (sud-asiatique). Usage prudent : peut "
            "résonner avec une partie de l'audience francophone d'origine indienne ou pakistanaise. "
            "À ne pas utiliser comme image générique d'engagement (risque de ciblage involontaire). "
            "À garder pour campagnes ciblées ou pour évoquer la diversité dans un thread sur "
            "'l'amour à travers les cultures'."
        ),
        "emotions": ["intimacy", "tradition", "commitment", "serenity"],
        "ambiance": ["ceremonial", "intimate"],
        "setting": ["wedding", "indoor"],
        "colors": ["warm", "amber", "blue_pastel", "gold"],
        "style_tags": ["wedding_photography", "close_up_hands", "cultural"],
        "cultural_specificity": "south_asian_wedding",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "close_up",
        "compaatible_fit": "low",
        "suggested_avatars": [9],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Spécificité culturelle marquée (mariage sud-asiatique). À éviter en image générique. Possible enjeu de droits si photo de mariage réelle.",
        "notes": "Format vertical. Image probablement issue de Pinterest mariage indien. Mains réelles, donc droits d'image potentiels.",
    },
    {
        "filename": "7f754c44f64d7f3e5167d4323da26c9c.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo publicitaire d'un yacht Riva luxe au coucher du soleil. Un couple est assis sur "
            "la plateforme arrière, en contre-jour, regardant l'horizon. La coque chromée du bateau "
            "reflète la lumière dorée du soleil. Le logo 'Riva' en typographie cursive blanche "
            "occupe le tiers inférieur sur fond turquoise. Image typique du marketing luxe nautique."
        ),
        "marketing_use": (
            "OFF-BRAND pour Compaatible. Le luxe ostentatoire (yacht de marque) ne correspond pas "
            "au positionnement Compaatible (premium précision, pas premium bling). À éviter pour "
            "tous les avatars. À garder potentiellement comme contre-exemple si on fait un thread "
            "type 'l'amour n'a pas besoin d'un yacht, il a besoin d'une bonne compatibilité de "
            "personnalité'."
        ),
        "emotions": ["aspirational", "distance", "wealth"],
        "ambiance": ["luxury", "sunset", "golden_hour", "polished"],
        "setting": ["outdoor", "sea", "yacht"],
        "colors": ["warm", "amber", "gold", "teal"],
        "style_tags": ["luxury_advertising", "brand_visible", "polished_commercial"],
        "cultural_specificity": "universal",
        "has_text_overlay": True,
        "text_content": "Riva",
        "quality_score": 8,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Logo de marque visible (Riva). Image publicitaire tierce, droits commerciaux. Positionnement luxe ostentatoire contraire à la marque Compaatible.",
        "notes": "Pinterest pin probablement issu d'une pub Riva. À ne pas réutiliser.",
    },
    {
        "filename": "f16df62472da30895b856d2705941cf6.jpg",
        "image_type": "anime_illustration",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Illustration anime d'un jeune couple debout face à face dans une prairie sous une pluie "
            "battante. Le garçon (cheveux noirs, veste marron, sac à dos) tend un parapluie bleu vers "
            "la fille (uniforme scolaire, queue de cheval brune). Deux petits corgis attendent à leurs "
            "pieds dans l'herbe. Le ciel est paradoxalement clair, bleu avec de gros nuages blancs "
            "cumulus, mais la pluie tombe en gouttes droites. Style légèrement éthéré, presque "
            "onirique. Composition centrée, équilibrée."
        ),
        "marketing_use": (
            "Image parfaite pour l'avatar 6 (Idéaliste Rêveur) en raison de son côté poétique et "
            "presque irréel. Aussi 7 (Jeune Mature) en raison du style anime/jeune. Bon support "
            "pour un tweet type 'On ne tombe pas amoureux, on reconnaît quelqu'un'. Le geste du "
            "parapluie tendu illustre l'idée de protection mutuelle."
        ),
        "emotions": ["tenderness", "wonder", "protection", "romance"],
        "ambiance": ["dreamy", "rainy", "fairy_tale", "poetic"],
        "setting": ["outdoor", "field", "grass"],
        "colors": ["cool", "muted", "blue", "green_grass"],
        "style_tags": ["anime_illustration", "ethereal", "shoujo_vibe"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 7, 5, 3],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format vertical. Possiblement généré IA. Format adapté aux stories et posts portrait.",
    },
    {
        "filename": "583c5600c8bf1e9cc55eee7b0e83e4e9.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo d'étreinte d'un couple en tenues traditionnelles sud-asiatiques de mariage. La "
            "mariée porte une robe rouge profonde brodée de motifs dorés complexes et de petits "
            "miroirs, son bras est couvert de bracelets noir et or et de motifs henné. Le marié, en "
            "tenue blanche brodée or, l'enlace par la taille, son alliance dorée visible. Cadrage "
            "serré sur les corps, pas de visages. Lumière chaude, presque crépusculaire. Ambiance "
            "très intime et noble."
        ),
        "marketing_use": (
            "Comme l'autre image culturelle (0948d30...), spécifiquement sud-asiatique. À usage "
            "ciblé uniquement. La force de l'image est l'intimité du geste (étreinte sans visages), "
            "qui pourrait inspirer une image générique 'étreinte sans visages' à recréer dans un "
            "contexte plus universel."
        ),
        "emotions": ["intimacy", "love", "devotion", "tenderness"],
        "ambiance": ["ceremonial", "warm", "cinematic"],
        "setting": ["wedding", "indoor"],
        "colors": ["warm", "burgundy", "red", "gold"],
        "style_tags": ["wedding_photography", "embrace", "cultural"],
        "cultural_specificity": "south_asian_wedding",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "close_up",
        "compaatible_fit": "low",
        "suggested_avatars": [9],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Mariage sud-asiatique. Même précaution que pour 0948d30.",
        "notes": "Image très soignée, palette burgundy proche de la palette Compaatible (#8B2D4A). À noter pour la cohérence visuelle si on développe un asset visuel custom.",
    },
    {
        "filename": "5a8c62d76f1f11cf408cb43f1c6393c0.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo vue de dos d'un jeune couple sur une plage brumeuse au crépuscule. Le garçon "
            "(pull vert kaki, brun) enlace la fille (manteau camel oversized, longs cheveux bruns, "
            "jean foncé, sac à main bordeaux). Ciel gris-blanc, sable mouillé, mer floue. Texte "
            "discret en bas-centre 'love u!' en blanc cursif. Esthétique 'Pinterest soft girl', "
            "automne, mélancolie douce."
        ),
        "marketing_use": (
            "Image très haute valeur pour Compaatible. Pas de visages = pas de problème de droits "
            "personnels marqué. Le texte 'love u!' léger renforce l'authenticité (style story Insta). "
            "Idéale pour les avatars 5 (Introverti, scène intime), 6 (Idéaliste, poésie), 7 (Jeune "
            "Mature, esthétique de génération), 9 (Séparé, redécouverte douce). Tons cool-warm "
            "automne très cohérents avec la palette Compaatible."
        ),
        "emotions": ["intimacy", "love", "peace", "melancholy_soft", "comfort"],
        "ambiance": ["dreamy", "soft", "autumn", "misty", "intimate"],
        "setting": ["beach", "outdoor", "fog"],
        "colors": ["muted", "cool", "warm", "camel", "burgundy", "green"],
        "style_tags": ["pinterest_aesthetic", "soft_focus", "from_behind", "lifestyle"],
        "cultural_specificity": "universal",
        "has_text_overlay": True,
        "text_content": "love u!",
        "quality_score": 9,
        "composition": "from_behind",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 7, 9, 11],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": "Photo lifestyle probablement issue d'Instagram. Vérifier les droits avant usage commercial ; usage organique inspirationnel acceptable.",
        "notes": "Format portrait. Excellent matching avec le ton de marque (40% émotionnel + 20% pratique). Référence visuelle idéale.",
    },
    {
        "filename": "93dd3c7ddfd2e9812c3bb57305e8c44b.jpg",
        "image_type": "photo_real",
        "subject_type": "body_part",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo POV : une main d'homme (avant-plan, blanche, jeune) tient la main d'une femme "
            "(chemisier blanc fluide, manche relevée jusqu'au coude, longue chevelure brune visible "
            "en arrière-plan flou). Doigts entrelacés. Sur son annulaire, deux bagues : un solitaire "
            "diamant en goutte et une bague en or fin. Au poignet, bracelet de perles dorées. Lumière "
            "douce bokeh derrière, contexte extérieur (peut-être un jardin). Style très Pinterest, "
            "saturation chaude."
        ),
        "marketing_use": (
            "Symbole iconique de l'engagement (bague de fiançailles + main tendue). À utiliser avec "
            "précaution car Compaatible cible les pré-engagement (matching), pas le post-engagement "
            "(mariage). Toutefois excellent visuel pour la promesse 'trouver la bonne personne'. "
            "Pour avatars 1 (Lucide) et 9 (Séparé) qui visualisent la prochaine étape réussie."
        ),
        "emotions": ["love", "commitment", "promise", "warmth", "anticipation"],
        "ambiance": ["soft", "golden_hour", "intimate", "warm"],
        "setting": ["outdoor", "garden"],
        "colors": ["warm", "amber", "white", "gold"],
        "style_tags": ["pinterest_aesthetic", "pov", "engagement_photo"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "pov",
        "compaatible_fit": "medium",
        "suggested_avatars": [1, 9, 6, 7],
        "suggested_platforms": ["twitter", "instagram"],
        "usage_warning": "Bague de fiançailles très visible : risque de signaler 'mariage' alors que Compaatible cible le matching pré-engagement. Utiliser plutôt pour évoquer 'la prochaine étape'.",
        "notes": "Bonne palette warm complémentaire à la palette Compaatible.",
    },
    {
        "filename": "e867ea47fa64e50de10a21b5543f68c8.jpg",
        "image_type": "graphic_text",
        "subject_type": "object_scene",
        "people_count": 0,
        "faces_visible": False,
        "description": (
            "Flat-lay Pinterest présentant deux tenues mises côte à côte sur fond gris pâle : à "
            "gauche une tenue femme (robe blanche plissée asymétrique épaule unique, talons nude, "
            "petit sac panier doré, boucles d'oreilles perles, collier fin) ; à droite une tenue "
            "homme (polo blanc, pantalon blanc taille haute, ceinture marron avec boucle V Valentino, "
            "pull camel jeté sur les épaules, mocassins beiges, montre or). En haut : titre élégant "
            "'N O N outfit / Styled by'. Aucune personne. Style mood-board mode."
        ),
        "marketing_use": (
            "OFF-TOPIC pour Compaatible. Le contenu est purement mode/fashion, sans personne ni "
            "élément relationnel. Ne convient à aucun avatar. À éviter dans tous les posts."
        ),
        "emotions": ["aspirational_style", "neutral"],
        "ambiance": ["clean", "minimal", "fashion"],
        "setting": ["studio"],
        "colors": ["muted", "neutral", "cream", "camel"],
        "style_tags": ["flatlay", "fashion_moodboard", "pinterest_outfit"],
        "cultural_specificity": "universal",
        "has_text_overlay": True,
        "text_content": "N O N outfit / Styled by",
        "quality_score": 7,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Logo Valentino visible (marque tierce). Contenu hors-sujet pour Compaatible.",
        "notes": "Pinterest fashion content. À retirer ou ne jamais utiliser.",
    },
]


def main() -> None:
    for i, meta in enumerate(SAMPLES, 1):
        new_id = insert_image(meta)
        print(f"[{i}/{len(SAMPLES)}] inserted id={new_id} fit={meta['compaatible_fit']} filename={meta['filename']}")
    print(f"\nTotal inserted: {len(SAMPLES)}")


if __name__ == "__main__":
    main()
