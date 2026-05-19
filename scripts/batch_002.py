"""Batch 002 : 10 images suivantes annotées le 2026-05-15."""
from insert_image import insert_image


BATCH = [
    {
        "filename": "0010644feb45569466d1db69c113bc75.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo nocturne ultra-cinématique d'un couple qui s'embrasse au milieu d'un festival "
            "des lanternes (style Yi Peng en Thaïlande ou Lantern Festival). Vue de profil légèrement "
            "de dos, le couple jeune s'enlace passionnément, la fille en sweat couleur safran tient "
            "le visage du garçon en sweat blanc. Au-dessus, des centaines de lanternes lumineuses "
            "blanches montent dans le ciel noir, créant un effet quasi-magique de constellation "
            "humaine. Autres festivaliers flous en arrière-plan."
        ),
        "marketing_use": (
            "Image extrêmement haute valeur visuelle pour Compaatible. Évocation puissante de "
            "l'amour vrai, du moment qui marque, du couple qui sort du reste du monde. Idéal "
            "pour les avatars 6 (Idéaliste), 7 (Jeune Mature), 9 (Séparé en reconstruction). "
            "Bon pour un thread Twitter sur 'à quoi ressemble une vraie rencontre' ou un post "
            "Reddit avec storytelling 'le moment où j'ai su que c'était différent'."
        ),
        "emotions": ["passion", "wonder", "love", "magic", "intimacy"],
        "ambiance": ["cinematic", "nighttime", "magical", "festival"],
        "setting": ["outdoor", "night", "festival", "asia_possibly"],
        "colors": ["dark", "warm", "amber", "black"],
        "style_tags": ["pinterest_aesthetic", "cinematic", "lifestyle_real", "instagram_story"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 10,
        "composition": "mid_shot",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 7, 9, 5],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": "Visages partiellement visibles (vue de côté). Photo réelle de tiers, vérifier le droit avant usage commercial. Acceptable en organique inspirationnel.",
        "notes": "Pinterest pin reconnu. Couleurs warm + dark cohérentes avec palette Compaatible (burgundy, dark plum).",
    },
    {
        "filename": "003051a902968158ca59e5537a0ef0c4.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Photo de couple souriant assis sur une chaise rembourrée bleu dans un restaurant chic "
            "à éclairage tamisé. L'homme jeune (lunettes, barbe courte, pull noir) entoure la femme "
            "par les épaules ; la femme (cheveux longs bruns, robe noire à motifs floraux dorés et "
            "argent, sandales noires à noeud) est assise sur ses genoux. Sourires détendus, regards "
            "vers la caméra. Table en bois en arrière-plan avec composition florale séchée. Vibe "
            "couple installé qui célèbre quelque chose."
        ),
        "marketing_use": (
            "Visages très clairement visibles : usage prudent car les personnes peuvent être "
            "identifiées et l'image ressemble fortement à un couple de personnalités publiques "
            "indiennes. Donc risque de droits + risque de rejet par l'audience qui les reconnaît. "
            "À usage très limité, plutôt référentiel."
        ),
        "emotions": ["happiness", "comfort", "love", "companionship"],
        "ambiance": ["warm", "intimate", "celebratory"],
        "setting": ["indoor", "restaurant"],
        "colors": ["warm", "dark", "gold", "black"],
        "style_tags": ["lifestyle_real", "candid", "instagram"],
        "cultural_specificity": "south_asian",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "mid_shot",
        "compaatible_fit": "low",
        "suggested_avatars": [],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Personnes très clairement identifiables, ressemblent à des personnalités publiques. À éviter sauf accord explicite.",
        "notes": "Ne pas réutiliser. Garder en DB comme référence négative.",
    },
    {
        "filename": "00390d8d7a6395d448926f8c580cffcb.jpg",
        "image_type": "photo_real",
        "subject_type": "group",
        "people_count": 5,
        "faces_visible": True,
        "description": (
            "Photo de groupe de 5 jeunes adultes sur le pont supérieur d'un yacht au coucher du "
            "soleil en Méditerranée (probablement Ibiza ou Formentera vu le style). Trois personnes "
            "assises avec des serviettes, deux couchées sur le côté, un garçon debout en polo gris. "
            "Bol de guacamole et chips au centre, smartphone visible. Ambiance fin de journée "
            "amis-vacances-luxe-soft."
        ),
        "marketing_use": (
            "Image de groupe d'amis luxe vacances. Ne correspond à AUCUN angle Compaatible "
            "(ce n'est ni couple, ni intimité, ni recherche d'amour). À ignorer pour les posts "
            "marketing."
        ),
        "emotions": ["friendship", "leisure", "summer_vibe"],
        "ambiance": ["luxury", "sunset", "summer", "social"],
        "setting": ["outdoor", "sea", "yacht"],
        "colors": ["warm", "amber", "blue"],
        "style_tags": ["lifestyle_real", "instagram", "group_friends"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Visages identifiables, photo perso de tiers. Pas pertinent pour Compaatible.",
        "notes": "Off-topic complet.",
    },
    {
        "filename": "00641b311d04710ebfc143d1c321d0ed.jpg",
        "image_type": "photo_real",
        "subject_type": "body_part",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo minimaliste nocturne : deux mains (l'une à gauche manucure rose pâle, l'autre à "
            "droite avec montre noire au poignet) forment ensemble la silhouette d'un coeur en se "
            "rejoignant index contre index et pouce contre pouce, sur un fond ciel nocturne étoilé "
            "noir. Au centre, un petit coeur gris flouté en superposition. Ambiance Pinterest "
            "aesthetic, story Instagram, granuleux."
        ),
        "marketing_use": (
            "Excellent visuel pour Compaatible : coeur formé à deux mains = symbole simple et "
            "universel du couple. Pas de visages = pas de problème de droits. Convient à tous "
            "les avatars émotionnels (5, 6, 7, 9). Idéal pour illustrer un post 'à deux on forme "
            "quelque chose qui n'existerait pas seul'."
        ),
        "emotions": ["love", "unity", "tenderness", "simplicity"],
        "ambiance": ["nighttime", "dreamy", "minimal", "starry"],
        "setting": ["outdoor", "night", "abstract"],
        "colors": ["dark", "black", "muted"],
        "style_tags": ["pinterest_aesthetic", "minimalist", "instagram_story"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "close_up",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 7, 9, 1],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Mains anonymes : pas de problème de droits.",
    },
    {
        "filename": "00678644e8ae666a63107801441a8481.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo cadrée mid-shot d'un couple assis sur un plaid à carreaux dans un parc en "
            "automne. À droite, un homme en jean foncé et veste denim joue d'une guitare acoustique "
            "(seul son torse et ses mains visibles, bottines en cuir country). À gauche, une femme "
            "en pull noir épais assise jambes repliées, sa main posée doucement sur la cuisse de "
            "l'homme (geste tendre, complice). Herbe sèche en arrière-plan flou. Vibe rustique, "
            "musique partagée, intimité simple."
        ),
        "marketing_use": (
            "Très haute valeur pour Compaatible. Pas de visages = pas de droits problématiques. "
            "Vibe slow + intimité = exactement la promesse Compaatible. Le geste de main qui "
            "se pose = langage du couple compatible (le 'silence à deux' de l'Idéaliste, avatar 6). "
            "Idéal pour un thread sur 'la vraie compatibilité, c'est savoir partager un silence' "
            "ou un post Reddit sur 'ce qui change quand tu trouves quelqu'un de compatible'."
        ),
        "emotions": ["tenderness", "intimacy", "calm", "complicity"],
        "ambiance": ["cozy", "autumn", "rustic", "soft"],
        "setting": ["outdoor", "park", "grass"],
        "colors": ["warm", "muted", "denim_blue", "earth"],
        "style_tags": ["lifestyle_real", "candid", "pinterest_aesthetic"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "mid_shot",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 9, 5, 1, 11],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Excellente palette automne, complémentaire au burgundy Compaatible.",
    },
    {
        "filename": "007a3b4a1d67eb39fda4debaf34672a5.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo noir et blanc vintage d'un drive-in cinéma américain des années 1940-1950. Vu "
            "depuis l'arrière d'une voiture décapotable, un couple est enlacé sur le siège arrière "
            "(épaule contre épaule, vue de dos). Plusieurs vieilles voitures alignées devant un "
            "grand écran qui projette un western (homme et femme en costume). Watermark visible en "
            "haut au centre 'Watermark Will Not Appear On Your Photo'."
        ),
        "marketing_use": (
            "Nostalgie pure mais OFF-BRAND pour Compaatible (B&W vintage = pas le ton de marque). "
            "Le watermark visible est rédhibitoire : impossible à utiliser tel quel. À ignorer."
        ),
        "emotions": ["nostalgia", "romance_vintage"],
        "ambiance": ["vintage", "cinematic", "black_white"],
        "setting": ["outdoor", "drive_in_cinema", "night"],
        "colors": ["black_white", "monochrome"],
        "style_tags": ["vintage", "black_white", "historical"],
        "cultural_specificity": "western",
        "has_text_overlay": True,
        "text_content": "Watermark Will Not Appear On Your Photo",
        "quality_score": 5,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "WATERMARK VISIBLE. Image stock à licence requise. Ne pas utiliser tel quel.",
        "notes": "Image stock photo avec watermark. À ignorer.",
    },
    {
        "filename": "008fb579877bf58140197be45f6ea4c7.jpg",
        "image_type": "photo_real",
        "subject_type": "object_scene",
        "people_count": 0,
        "faces_visible": False,
        "description": (
            "Chambre romantique style chalet de montagne : grand lit blanc en bois brut surélevé "
            "sur structure massive, entièrement recouvert d'une marée de pétales de roses rouges. "
            "Pétales également répandus sur le sol en pierre claire. À droite, baie vitrée donnant "
            "sur des montagnes verdoyantes brumeuses. Mur en pierre brute + poutres apparentes. "
            "Setup type 'honeymoon suite' ou anniversaire de mariage."
        ),
        "marketing_use": (
            "Le setup pétales de rose = engagement / honeymoon, pas Compaatible (matching). "
            "Risque de signaler le mauvais funnel (Compaatible cible les pré-couple, pas les "
            "anniversaires de mariage). À utiliser éventuellement comme contre-exemple ('on ne "
            "te promet pas des pétales de rose au premier rendez-vous, on te promet une vraie "
            "compatibilité')."
        ),
        "emotions": ["romance_cheesy", "luxury", "celebration"],
        "ambiance": ["luxury", "honeymoon", "scenic"],
        "setting": ["indoor", "bedroom", "mountain_view"],
        "colors": ["warm", "red", "wood", "white"],
        "style_tags": ["luxury_setup", "scenic", "pinterest"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "wide",
        "compaatible_fit": "low",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Risque de signaler 'mariage' au lieu de 'rencontre'. Pas de personnes mais setup luxe.",
        "notes": "Pinterest type 'romantic getaway'. Low fit Compaatible.",
    },
    {
        "filename": "009497fcc10b7c6393fcbdf573c909a9.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Diptyque vertical de deux captures d'écran d'une série télévisée (visuellement 'The "
            "Office' US, scènes entre Pam et Jim). Image du haut : femme aux cheveux blond-roux "
            "en queue de cheval, débardeur clair, qui sourit timidement penchée en avant. Image "
            "du bas : homme en chemise blanche col ouvert sous costume noir, regard amusé et "
            "sourire complice."
        ),
        "marketing_use": (
            "Référence pop-culture forte (couple Jim/Pam de The Office, archétype 'la bonne "
            "personne sous nos yeux'). Très partageable pour les avatars 7 (Jeune Mature) et 2 "
            "(Sceptique Connecté). MAIS image copyrightée Universal/NBC. Usage commercial "
            "interdit. À utiliser uniquement en organique meme-friendly avec disclaimer mental "
            "(et idéalement reformulé en visuel original)."
        ),
        "emotions": ["complicity", "tenderness", "tension_romantique"],
        "ambiance": ["nostalgia_tv", "intimate"],
        "setting": ["indoor", "office"],
        "colors": ["warm", "muted"],
        "style_tags": ["tv_screenshot", "meme_friendly", "pop_culture"],
        "cultural_specificity": "western_pop_culture",
        "has_text_overlay": False,
        "quality_score": 6,
        "composition": "close_up",
        "compaatible_fit": "low",
        "suggested_avatars": [7, 2],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Copyright NBC Universal (The Office). Pas d'usage commercial. Memes organiques uniquement.",
        "notes": "Référence Jim/Pam. Plutôt à recréer en photographie originale avec acteurs Compaatible si on veut l'angle.",
    },
    {
        "filename": "00a48118e4d7144d6cba684889e95617.jpg",
        "image_type": "photo_real",
        "subject_type": "object_scene",
        "people_count": 0,
        "faces_visible": False,
        "description": (
            "Photo en lumière chaude tamisée d'un dîner romantique en intérieur. Petite table ronde "
            "en bois pour deux avec deux assiettes (pâtes blanches et tartines beurrées) sur jolis "
            "sets de table imprimés, deux verres à vin en cristal, une seule bougie blanche allumée "
            "centrale, vase avec bouquet de roses rouges et fleurs blanches. Mur peint crème, cadres "
            "fleurs vintage, étagère cuisine en arrière-plan avec vaisselle. Aucune personne mais "
            "ambiance 'home date night'."
        ),
        "marketing_use": (
            "Excellent pour Compaatible. Symbole de la rencontre intime sans afficher des visages. "
            "Aucun risque de droits personnels. Ambiance 'maison + simple' = anti-Tinder-meets-in-a-bar. "
            "Convient particulièrement aux avatars 5 (Introverti, scène intime safe), 7 (Jeune "
            "Mature, 'je veux un amour calme'), 9 (Séparé, redécouverte douce), 11 (Parent Solo, "
            "le moment rare où c'est juste vous deux)."
        ),
        "emotions": ["intimacy", "warmth", "calm", "anticipation"],
        "ambiance": ["cozy", "candlelit", "intimate", "home"],
        "setting": ["indoor", "dining_room", "home"],
        "colors": ["warm", "amber", "cream", "red"],
        "style_tags": ["lifestyle_real", "candid", "pinterest_aesthetic", "moody_warm"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 7, 9, 11, 6],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Très haute valeur. Pas de personnes = libre d'usage si la photo est libre de droits Pinterest.",
    },
    {
        "filename": "00a69e115aa9cf54a93560719c8376ae.jpg",
        "image_type": "photo_real",
        "subject_type": "object_scene",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Photo nocturne ambiance restaurant : un iPhone posé contre un boîte en bois sur une "
            "table de restaurant, affichant à l'écran un selfie miroir d'un couple jeune (femme à "
            "gauche avec haut violet, garçon à droite en t-shirt blanc, vu dans un miroir extérieur "
            "type ascenseur). Au premier plan, une coupe de tiramisu généreuse, un verre vide et "
            "une carafe d'eau. Filtre vintage warm, presque sépia. Ambiance 'date du soir'."
        ),
        "marketing_use": (
            "Image très moderne, méta (selfie dans la photo). Évoque l'archivage du couple dans "
            "le téléphone, les souvenirs partagés. Convient à l'avatar 7 (Jeune Mature) qui "
            "consomme ce type d'esthétique. Faces visibles sur l'écran : usage prudent."
        ),
        "emotions": ["nostalgia", "intimacy", "complicity", "warmth"],
        "ambiance": ["warm", "nighttime", "restaurant", "vintage_filter"],
        "setting": ["indoor", "restaurant", "night"],
        "colors": ["warm", "amber", "sepia"],
        "style_tags": ["lifestyle_real", "instagram_story", "vintage_filter", "meta"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "close_up",
        "compaatible_fit": "medium",
        "suggested_avatars": [7, 6, 9],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Visages visibles sur l'écran du téléphone. Photo perso de tiers, vérifier droits avant usage.",
        "notes": "Format portrait. Bonne ambiance restaurant date du soir, mais visages identifiables.",
    },
]


def main() -> None:
    for i, meta in enumerate(BATCH, 1):
        new_id = insert_image(meta)
        print(f"[{i}/{len(BATCH)}] id={new_id} fit={meta['compaatible_fit']:10s} avatars={meta['suggested_avatars']}")
    print(f"\nBatch 002: {len(BATCH)} images inserted.")


if __name__ == "__main__":
    main()
