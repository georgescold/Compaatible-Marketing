"""Batch 004 : 15 images (01f9 a 0396ce)."""
from insert_image import insert_image

BATCH = [
    {
        "filename": "01f9c7404314763ed42aedfb4a54a03a.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Capture d'ecran du film '13 Going on 30' : Jennifer Garner (t-shirt blanc imprime roses, jupe beige) et Mark Ruffalo (chemise bleu pale) sont debout cote a cote la nuit, en bord de fleuve avec les lumieres d'une ville en arriere-plan flou. Elle tient un paquet de chewing-gum Razzles. Sourires complices, regards qui se cherchent."
        ),
        "marketing_use": (
            "Reference pop culture forte du couple 'on aurait du etre ensemble plus tot' (le film entier parle de retrouver l'evidence). Convient avatar 1 (Lucide) sur le theme du 'temps perdu', 9 (Separee) sur le 'retour a l'evidence'. MAIS image copyrightee (Sony Pictures 2004). Usage organique meme uniquement."
        ),
        "emotions": ["romance", "nostalgia", "complicity"],
        "ambiance": ["cinematic", "nighttime", "soft"],
        "setting": ["outdoor", "urban", "night"],
        "colors": ["warm", "muted", "blue"],
        "style_tags": ["tv_film_screenshot", "pop_culture", "meme_friendly"],
        "cultural_specificity": "western_pop_culture",
        "has_text_overlay": False,
        "quality_score": 6,
        "composition": "mid_shot",
        "compaatible_fit": "low",
        "suggested_avatars": [1, 9],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Copyright Sony Pictures (13 Going on 30, 2004). Meme organique uniquement.",
        "notes": "Visages identifiables (acteurs celebres).",
    },
    {
        "filename": "01fe34bedb901efefb26a622a6ac78dc.jpg",
        "image_type": "anime_illustration",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Illustration anime/comics avec Spider-Man (costume rouge/bleu, accroupi sur un rebord) et Spider-Gwen (costume blanc/noir/violet, capuche blanche). Ils se font face de chaque cote d'une faille verticale de lumiere rose neon qui traverse l'image. Ciel nocturne etoile avec pleine lune. Coucher de soleil orange-rose au loin sur la ville. Leurs mains se touchent au centre de la lumiere. Style 'Spider-Verse'."
        ),
        "marketing_use": (
            "Image symbolique forte : 'deux univers separes qui se rencontrent'. Tres pertinent pour Compaatible (la rencontre entre deux profils, deux mondes, qui se trouvent). Pop culture donc copyright Marvel. Usage organique uniquement. Avatars 6 (Idealiste, magie de la rencontre) et 7 (Jeune Mature, esthetique de generation)."
        ),
        "emotions": ["wonder", "magic", "connection", "longing"],
        "ambiance": ["dreamy", "nighttime", "magical", "cinematic"],
        "setting": ["outdoor", "rooftop", "night", "city"],
        "colors": ["pink_neon", "blue", "warm_accent", "dark"],
        "style_tags": ["anime_illustration", "comics_style", "pop_culture", "spider_verse"],
        "cultural_specificity": "western_pop_culture",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "wide",
        "compaatible_fit": "low",
        "suggested_avatars": [6, 7],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Personnages Marvel (Spider-Man / Spider-Gwen). Copyright Disney/Marvel. Usage organique uniquement.",
        "notes": "Format portrait. Concept tres reutilisable en visuel original.",
    },
    {
        "filename": "0227e7a256f6b5c3131496178e7b45b3.jpg",
        "image_type": "photo_real",
        "subject_type": "single_person",
        "people_count": 1,
        "faces_visible": True,
        "description": (
            "Photo d'une jeune femme debout sur la plage au bord des vagues, robe longue blanche en dentelle a fines bretelles. Cheveux longs bruns lachés au vent. Main posee sur son front (geste de regard au loin ou contre le vent). Ciel gris-blanc nuageux, mer agitee avec rochers et ecume. Sable mouillé. Posture decontractee mais reflechie."
        ),
        "marketing_use": (
            "Femme seule contemplative au bord de l'ocean = forte resonance avec avatar 5 (Introvertie, scenes intimes solo), 6 (Idealiste reveuse), 9 (Separee). Visage visible donc verifier droits avant usage commercial. Couleurs douces, mood melancolique."
        ),
        "emotions": ["contemplation", "softness", "melancholy", "solitude"],
        "ambiance": ["soft", "overcast", "calm", "nature"],
        "setting": ["outdoor", "beach", "sea"],
        "colors": ["muted", "white", "grey", "cool"],
        "style_tags": ["lifestyle_real", "pinterest_aesthetic", "soft_girl"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "wide",
        "compaatible_fit": "medium",
        "suggested_avatars": [5, 6, 9],
        "suggested_platforms": ["instagram", "organic_only"],
        "usage_warning": "Visage identifiable. Photo personnelle de tiers probable, verifier droits.",
        "notes": "Format portrait.",
    },
    {
        "filename": "0271f48e207e8c0eeb57eeddd0bf6625.jpg",
        "image_type": "photo_real",
        "subject_type": "object_scene",
        "people_count": 0,
        "faces_visible": False,
        "description": (
            "Photo d'une guitare acoustique en bois clair posee debout contre le tronc massif d'un grand arbre. Sol couvert d'aiguilles de pin orange. Lumiere chaude crepusculaire. Forest aesthetic. Aucune personne."
        ),
        "marketing_use": (
            "Objet seul sans personne, pas directement utile pour Compaatible (qui parle de couples / relations). Pourrait servir en illustration secondaire pour un post sur 'le silence' ou 'l'attente'. Faible priorite."
        ),
        "emotions": ["calme", "solitude_douce", "nostalgia"],
        "ambiance": ["forest", "warm", "sunset"],
        "setting": ["outdoor", "forest"],
        "colors": ["warm", "amber", "earth"],
        "style_tags": ["pinterest_aesthetic", "object_photo", "moody"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "wide",
        "compaatible_fit": "low",
        "suggested_avatars": [6],
        "suggested_platforms": ["organic_only"],
        "usage_warning": None,
        "notes": "Pas de personnes = libre d'usage.",
    },
    {
        "filename": "0285d19b187ed0bedf64c976575c0cec.jpg",
        "image_type": "painting",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Illustration silhouette : un couple est assis face a face sur une balancoire en bois suspendue a la branche d'un grand arbre. Coucher de soleil vibrant en arriere-plan (jaune, orange, rose, mauve, bleu degrades). Tout est en silhouette noire. La femme a les cheveux longs au vent, ils se tiennent les mains. Style affiche / illustration vectorielle stylisee."
        ),
        "marketing_use": (
            "Image symbolique tres reutilisable : couple symbol sans identite donc parfait pour eviter tous les problemes de droits. Convient avatars 6 (Idealiste, scene reveuse), 7 (Jeune Mature, romantique calme), 9 (Separee, image de retour a l'evidence). Bon pour un visuel d'accompagnement de tweet."
        ),
        "emotions": ["romance", "calme", "wonder", "tenderness"],
        "ambiance": ["sunset", "dreamy", "idyllique"],
        "setting": ["outdoor", "nature", "tree"],
        "colors": ["warm", "orange", "purple", "yellow"],
        "style_tags": ["illustration", "silhouette", "vector_style"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 7, 9],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Illustration sans signature - usage libre en pratique.",
    },
    {
        "filename": "0292e5788e51df3e8713da39e2e225a6.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo tres granuleuse / vintage sepia d'un couple ages (silhouettes sombres) qui se tient debout cote a cote au bord de la mer, regardant vers les vagues. Le sable beige, la mer grise-beige, le ciel uniformement gris-sepia. Aucun detail visible des visages ou vetements. Composition simple, melancolique, intemporelle."
        ),
        "marketing_use": (
            "Symbole fort de la longevite du couple = exactement la promesse Compaatible (couples qui durent grace a la compatibilite). Tres reutilisable : pas d'identite, ambiance intemporelle. Convient avatars 1 (Lucide, vision de l'amour qui dure), 9 (Separee, ce qu'on veut retrouver)."
        ),
        "emotions": ["longevity", "calme", "tenderness", "nostalgia"],
        "ambiance": ["vintage", "calme", "intemporel"],
        "setting": ["outdoor", "beach", "sea"],
        "colors": ["sepia", "muted", "grey"],
        "style_tags": ["vintage", "film_grain", "minimalist"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [1, 9, 6],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait etire. Pas de visages = libre.",
    },
    {
        "filename": "02cf7a6dd277cdc4fbe24464d4c41cf7.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo nocturne intime : un couple s'embrasse sous un projecteur exterieur cylindrique qui projette un halo lumineux sur le mur blanc. La femme (longs cheveux bruns ondules, debardeur blanc, montre carree dorée au poignet) est plaquee contre le mur, sa main posee a plat sur le mur. L'homme l'enlace, sa veste sombre visible. Tatouage discret au poignet de la femme. Ambiance balcon ou terrasse, ville sombre en arriere-plan flou."
        ),
        "marketing_use": (
            "Image phare : intimite, passion contenue, scene de couple sans visages identifiables. Forte resonance avec avatars 6 (Idealiste, scene cinematique), 9 (Separee retrouvant l'intensite), 7 (Jeune Mature). Palette warm/dark coherente avec Compaatible."
        ),
        "emotions": ["passion", "intimacy", "tenderness", "intensity"],
        "ambiance": ["nighttime", "cinematic", "intimate", "moody"],
        "setting": ["outdoor", "balcony", "night"],
        "colors": ["warm", "amber", "dark"],
        "style_tags": ["pinterest_aesthetic", "lifestyle_real", "cinematic"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "mid_shot",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 9, 7, 5],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Tres reutilisable.",
    },
    {
        "filename": "02e74545e43e9ff055b27f485fcf8e97.jpg",
        "image_type": "graphic_text",
        "subject_type": "object_scene",
        "people_count": 0,
        "faces_visible": False,
        "description": (
            "Collage de captures d'ecran de pochettes d'albums Spotify : Heat Waves (Glass Animals), Eminem, Minefields (Faouzia/John Legend), Taylor Swift 1989, Justin Bieber, The Weeknd, Adele, etc. Mise en page rectangulaire serree avec interfaces Spotify (boutons play, sous-titres morceaux). Tons noir / sepia. Pure aesthetic 'music playlist mood'."
        ),
        "marketing_use": (
            "OFF_BRAND : c'est du contenu musical generation Z / Pinterest, pas pertinent pour Compaatible. Pas de couple, pas d'image relationnelle. A ignorer."
        ),
        "emotions": ["nostalgia", "youth", "music_mood"],
        "ambiance": ["dark", "playlist", "gen_z"],
        "setting": ["abstract"],
        "colors": ["dark", "black_white", "sepia"],
        "style_tags": ["spotify_screenshots", "pinterest_aesthetic", "collage"],
        "cultural_specificity": "western_pop_culture",
        "has_text_overlay": True,
        "text_content": "Heat Waves, Bad Guy, Stan, 1989, etc.",
        "quality_score": 5,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Pochettes d'albums copyrighted (Universal, Warner, Sony, etc.). Pas d'usage commercial.",
        "notes": "A ignorer pour Compaatible.",
    },
    {
        "filename": "0321cef01c59037a48dac9800ddd0299.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo style coreen/asiatique : un couple jeune assis cote a cote devant la vitrine d'un fleuriste. Tous deux cachent leur visage derriere un enorme bouquet de fleurs : lui (jean denim, pull bleu) tient des marguerites/asters roses ; elle (manteau marron camel, robe imprimee fleurie) tient des marguerites blanches. Lumiere chaude depuis l'interieur du magasin. Filtre vintage."
        ),
        "marketing_use": (
            "Image PARFAITE pour Compaatible : couple symbol sans identite (visages caches), reference universelle, ton tres warm Pinterest, gestes synchronises = compatibilite. Avatars 5 (Introvertie, geste pudique), 6 (Idealiste, poesie), 7 (Jeune Mature, esthetique coreenne), 9 (Separee). Top tier reutilisabilite."
        ),
        "emotions": ["tenderness", "complicity", "playful", "pudeur"],
        "ambiance": ["cozy", "warm", "intimate", "vintage_filter"],
        "setting": ["outdoor", "street", "shop"],
        "colors": ["warm", "muted", "earth", "rose"],
        "style_tags": ["pinterest_aesthetic", "korean_aesthetic", "lifestyle_real"],
        "cultural_specificity": "asian",
        "has_text_overlay": False,
        "quality_score": 10,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 7, 9, 11],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Image iconique. Tres haute valeur visuelle.",
    },
    {
        "filename": "032d2f0e4c3c2eb1105eba2d060b4dc4.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo de dos d'un couple allonge sur la plateforme arriere d'un yacht qui file sur la mer. Sillage blanc derriere. Montagnes verdoyantes a l'horizon, ciel bleu legerement nuageux. Lui en blanc, elle en robe blanche imprimee. Position decontractee, ses jambes ramenees sur lui. Vacances luxe."
        ),
        "marketing_use": (
            "OFF_BRAND : luxe ostentatoire (yacht) + photo couple flexant un lifestyle 'instagram travel influencer'. Pas le territoire Compaatible (premium precision, pas premium luxe)."
        ),
        "emotions": ["luxe", "leisure", "summer"],
        "ambiance": ["luxury", "summer", "sea"],
        "setting": ["outdoor", "sea", "yacht"],
        "colors": ["white", "blue", "warm"],
        "style_tags": ["luxury_lifestyle", "instagram_travel", "lifestyle_real"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Luxe ostentatoire incompatible avec Compaatible.",
        "notes": "A ignorer.",
    },
    {
        "filename": "034c195c9b77960c65ed234924bf7906.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo nocturne style coreen K-drama : une jeune femme en sweat-shirt creme et short, cheveux longs marche dans une rue residentielle pavee. A 3 metres derriere elle, un homme en jean fonce et sweat noir, capuche, marche dans le meme sens. Arbres, lampadaires, route. Ambiance scenes de fin de soiree / 'il me raccompagne sans rien dire'. Filtre vert-bleu nocturne moody."
        ),
        "marketing_use": (
            "Image cinematique forte pour 'la tension douce du debut'. Convient avatars 7 (Jeune Mature, esthetique K-drama), 6 (Idealiste, scenes precieuses), 5 (Introvertie, intimite hesitante). Top reutilisabilite : pas de visages, image symbolique du 'moment qui pourrait basculer'."
        ),
        "emotions": ["tension_douce", "anticipation", "tenderness", "longing"],
        "ambiance": ["nighttime", "cinematic", "moody", "k_drama"],
        "setting": ["outdoor", "street", "night"],
        "colors": ["dark", "green_blue", "muted"],
        "style_tags": ["pinterest_aesthetic", "k_drama_aesthetic", "cinematic"],
        "cultural_specificity": "asian",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [7, 6, 5, 9],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format carre.",
    },
    {
        "filename": "034e62c9a312fbeec469e31b859f4a0c.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Photo de mariage haut de gamme : une mariee (robe bustier blanche en satin, pantalon de smoking blanc large, escarpins beiges, sac Dior Lady) est assise dans une vieille voiture decapotable beige des annees 60. Le marie (costume gris clair, cravate grise) la regarde depuis le siege passager, sa main pres de son visage. En arriere-plan, un manoir/chateau en pierre couvert de lierre vert, tables de mariage installees sur la pelouse."
        ),
        "marketing_use": (
            "Wedding context tres marque (robe mariee + sac de luxe + chateau). Compaatible cible le pre-engagement, donc cette image signale le mauvais funnel. Bons visuels mais pas alignes avec le moment de matching. A garder uniquement pour visualiser 'la prochaine etape ideale' avec parcimonie."
        ),
        "emotions": ["luxury", "elegance", "romance"],
        "ambiance": ["wedding", "luxury", "vintage", "elegant"],
        "setting": ["outdoor", "castle", "wedding"],
        "colors": ["white", "beige", "cream", "warm"],
        "style_tags": ["wedding_photography", "luxury_lifestyle", "vintage_car"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "wide",
        "compaatible_fit": "low",
        "suggested_avatars": [6],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Visages identifiables. Wedding context + marque Dior visible = double risque (droits + signal de mauvais funnel).",
        "notes": "Photo perso d'influenceur probablement.",
    },
    {
        "filename": "0350b23361b3203a1304fdac49c8fa11.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo POV classique 'follow me' : main de femme tient la main d'un homme qui marche devant, dos a la camera. Lui : chemise blanche, dos visible, cheveux noirs courts. Allee bordee d'arbres verdoyants ensoleilles. Lumiere chaude printemps. Bracelet en bois sur le poignet de l'homme. Sentier en pierres."
        ),
        "marketing_use": (
            "POV 'follow me' = symbole universel du couple complice qui avance ensemble. Tres reutilisable, pas de visages. Convient tous avatars amoureux : 5, 6, 7, 9. Pour un tweet sur 'avancer ensemble' / 'la bonne personne te guide'."
        ),
        "emotions": ["complicity", "guidance", "tenderness", "anticipation"],
        "ambiance": ["soft", "spring", "outdoor", "warm"],
        "setting": ["outdoor", "garden", "path"],
        "colors": ["green", "white", "warm"],
        "style_tags": ["pinterest_aesthetic", "pov", "follow_me"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "pov",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 7, 9],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format presque carre.",
    },
    {
        "filename": "038ed6ceba09d1eedb6e95028f668be5.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo editoriale dans la cour interieure d'un vieux manoir en pierre couvert de lierre. Un couple danse : l'homme (chemise blanche, pantalon blanc) fait tourner la femme (robe ivoire longue, longs cheveux brun fonce). Vu a travers une arche en pierre depuis l'interieur, ce qui cree un cadrage 'tableau'. Lumiere chaude couchante. Style 'engagement photoshoot' haut de gamme."
        ),
        "marketing_use": (
            "Tres bel image conte de fees, mais le code 'photoshoot engagement' la rapproche du mariage. Compaatible cible le matching pre-engagement, donc utiliser cette image avec prudence pour eviter le signal 'on est deja fiance'. Convient avatar 6 (Idealiste, conte de fees) mais a doser."
        ),
        "emotions": ["romance", "elegance", "wonder", "dance"],
        "ambiance": ["fairy_tale", "golden_hour", "elegant", "cinematic"],
        "setting": ["outdoor", "castle", "courtyard"],
        "colors": ["green_ivy", "stone", "warm", "ivory"],
        "style_tags": ["editorial_photography", "engagement_aesthetic", "cinematic"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "wide",
        "compaatible_fit": "medium",
        "suggested_avatars": [6, 9],
        "suggested_platforms": ["instagram", "organic_only"],
        "usage_warning": "Registre 'engagement photoshoot' qui peut signaler le mauvais funnel.",
        "notes": "Format portrait. Tres beau visuel mais a utiliser avec parcimonie.",
    },
    {
        "filename": "0396ceace667111622701b78409c4e4c.jpg",
        "image_type": "anime_illustration",
        "subject_type": "single_person",
        "people_count": 1,
        "faces_visible": True,
        "description": (
            "Rendu 3D / illustration realiste de style 'WhatsApp dp' sud-asiatique : un homme barbu dort sur un oreiller blanc, t-shirt blanc, draps clairs. Au-dessus de sa tete, une bulle de pensee qui montre le meme homme enlacant une femme (cheveux noirs, sari traditionnel avec broderie bleue). Decor bleu nuit avec etoile. Style 'AI generated greeting card' tres kitsch."
        ),
        "marketing_use": (
            "OFF_BRAND : esthetique 'WhatsApp DP / greeting card' qui ne correspond ni au ton de marque Compaatible (premium / precision) ni a son audience (francais 25-40). Plus image d'envoi WhatsApp Indien que reference Compaatible."
        ),
        "emotions": ["longing", "kitsch_romance"],
        "ambiance": ["nighttime", "kitsch", "stylized"],
        "setting": ["indoor", "bedroom"],
        "colors": ["blue", "white", "warm"],
        "style_tags": ["ai_3d_render", "kitsch", "whatsapp_dp", "greeting_card"],
        "cultural_specificity": "south_asian",
        "has_text_overlay": False,
        "quality_score": 4,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Style kitsch culturellement specifique. Incompatible ton Compaatible.",
        "notes": "A ignorer.",
    },
]


def main() -> None:
    for i, meta in enumerate(BATCH, 1):
        new_id = insert_image(meta)
        print(f"[{i}/{len(BATCH)}] id={new_id} fit={meta['compaatible_fit']:10s} avatars={meta['suggested_avatars']}")
    print(f"\nBatch 004: {len(BATCH)} inserted.")


if __name__ == "__main__":
    main()
