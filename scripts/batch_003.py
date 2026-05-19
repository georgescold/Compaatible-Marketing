"""Batch 003 : 15 images (00ae a 01f282)."""
from insert_image import insert_image

BATCH = [
    {
        "filename": "00ae1787e59e1bb94e17ae00949b1b14.jpg",
        "image_type": "photo_real",
        "subject_type": "single_person",
        "people_count": 1,
        "faces_visible": False,
        "description": (
            "Photo nocturne stylisee, fond noir presque total avec une silhouette de jeune femme floutee tenant un appareil photo ou un objet (la silhouette occupe le centre droit). En bas, un fragment de ciel violet et orange brulant a travers des fils electriques. Esthetique 'aesthetic dark', presque irreelle. Watermark 'Youtube: CHEALY' en haut a droite."
        ),
        "marketing_use": (
            "Watermark visible rend l'image inutilisable telle quelle. La silhouette + ciel pourrait inspirer du contenu original mais on ne reutilise pas directement. A garder en reference visuelle, pas en pool de posts."
        ),
        "emotions": ["mystery", "solitude", "wonder"],
        "ambiance": ["nighttime", "moody", "aesthetic_dark"],
        "setting": ["outdoor", "night", "urban"],
        "colors": ["dark", "violet", "warm_accent"],
        "style_tags": ["aesthetic_dark", "youtube_thumbnail", "silhouette"],
        "cultural_specificity": "universal",
        "has_text_overlay": True,
        "text_content": "Youtube: CHEALY",
        "quality_score": 5,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "WATERMARK visible (Youtube: CHEALY). Ne pas reutiliser.",
        "notes": "Tres faible info utile.",
    },
    {
        "filename": "00cfe06b9dcdcc026b8cc66b19906b8c.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo aerienne d'un couple qui s'embrasse dans un lit en exterieur sur une plateforme suspendue de cabane balinaise (style Bali ou Ubud). Filet de securite, draps blancs froisses, oreillers, jungle dense de palmiers verts a perte de vue. Le couple est blotti centre, vue de dessus, jambes nues. Atmosphere de retraite intime, paradisiaque mais authentique. Lumiere du matin."
        ),
        "marketing_use": (
            "Image tres forte pour evoquer l'intimite vraie d'un couple compatible. La nature massive en arriere-plan = profondeur. Pas de visage clair = pas de probleme de droits. Convient avatars 6 (Idealiste, decor reveur), 9 (Sepa repassant a la phase 'on s'est trouves'), 5 (Introverti, intimite preservee)."
        ),
        "emotions": ["intimacy", "love", "passion_calme", "serenite"],
        "ambiance": ["dreamy", "cinematic", "tropical", "morning"],
        "setting": ["outdoor", "jungle", "treehouse", "bed"],
        "colors": ["green", "white", "muted", "warm"],
        "style_tags": ["lifestyle_aerial", "pinterest_aesthetic", "instagram_travel"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 9, 5, 7],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Tres haute valeur visuelle.",
    },
    {
        "filename": "00de1da4731146b33041d3da47bf371e.jpg",
        "image_type": "photo_real",
        "subject_type": "object_scene",
        "people_count": 1,
        "faces_visible": False,
        "description": (
            "Photo nocturne d'un show de flyboard (jet propulse a eau) avec gerbes d'etincelles dorees formant un arc spectaculaire au-dessus d'un yacht luxueux. Drapeau americain visible. Reflets rouges et bleus sur l'eau noire. Pyrotechnie. Spectacle commercial de luxe."
        ),
        "marketing_use": (
            "OFF_BRAND total : luxe ostentatoire, drapeau US, spectacle bling. Aucun rapport avec la rencontre amoureuse profonde. A ignorer."
        ),
        "emotions": ["spectacle", "luxury", "distance"],
        "ambiance": ["luxury", "nighttime", "fireworks"],
        "setting": ["outdoor", "sea", "yacht", "night"],
        "colors": ["dark", "warm_amber", "red"],
        "style_tags": ["luxury_lifestyle", "instagram_flex"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 6,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Luxe ostentatoire incompatible avec la marque Compaatible.",
        "notes": "A ignorer.",
    },
    {
        "filename": "00e72f8978567397fe5bbb242c4b76a4.jpg",
        "image_type": "photo_real",
        "subject_type": "single_person",
        "people_count": 1,
        "faces_visible": False,
        "description": (
            "Photo de dos d'une jeune femme regardant un coucher de soleil sur la mer. Cheveux longs en queue de cheval, pull blanc casque (lettre M visible au col). Le ciel pastel rose-violet-bleu transitionne doucement. Bateau lointain a peine visible. Cadrage carre. Ambiance contemplative, solo, douce melancolie. Esthetique very Pinterest 'soft girl'."
        ),
        "marketing_use": (
            "Image phare pour l'avatar 5 (Introverti Profondement Seul) : femme seule contemplative au crepuscule, pas de drama, juste un silence pesant. Aussi 6 (Idealiste : attente) et 9 (Separee en reconstruction). Excellente pour un tweet 'Tu n'as pas rate l'amour. L'amour ne t'a juste jamais croisee'."
        ),
        "emotions": ["solitude", "melancholy", "contemplation", "softness"],
        "ambiance": ["sunset", "soft", "dreamy", "quiet"],
        "setting": ["outdoor", "beach", "sea"],
        "colors": ["pastel", "pink", "violet", "white"],
        "style_tags": ["pinterest_aesthetic", "from_behind", "soft_girl"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "from_behind",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 9],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format carre. Excellente reference visuelle pour le ton 'introvertie melancolique'.",
    },
    {
        "filename": "01024def1f67fea78888732b6826629f.png",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo en contre-jour d'un couple silhouette qui s'enlace dans une piece intime, un grand abat-jour blanc en plein centre dessus de leurs visages presque cache. Mur orange-brun en fond, cadres anciens, ambiance retro intimiste. La femme en robe sombre, l'homme en chemise claire. Etreinte tendre, danse douce ou slow."
        ),
        "marketing_use": (
            "Tres puissant visuellement. La silhouette + lampe = symbole de l'intimite du couple (le 'monde a deux' dans le halo de lumiere). Convient avatars 6 (Idealiste, scene cinematique) et 1 (Lucide, image qui resume le 'couple installe qui dure'). Bon pour un tweet poetique sur 'l'amour ne se voit pas, il se vit dans le halo'."
        ),
        "emotions": ["intimacy", "tenderness", "passion_douce", "calme"],
        "ambiance": ["intimate", "warm", "cinematic", "moody"],
        "setting": ["indoor", "home", "vintage"],
        "colors": ["warm", "amber", "brown", "dark"],
        "style_tags": ["cinematic", "silhouette", "moody", "retro"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 10,
        "composition": "mid_shot",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 1, 9, 7],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Image iconique. Format portrait, palette warm coherente avec Compaatible.",
    },
    {
        "filename": "010f91ed7ad8b5db2e51965afd8b21e2.jpg",
        "image_type": "photo_real",
        "subject_type": "body_part",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo intime serree : un homme en chemise carreaux noir-blanc tient delicatement la main d'une jeune femme en robe vert citron. Il dessine au stylo coloriste/henne sur le dos de sa main. Bracelets multicolores au poignet de la femme. Bague d'argent au pouce de l'homme. Coque de telephone noire et blanche posee. Cadrage POV dessus. Watermark @amweirdoo en bas."
        ),
        "marketing_use": (
            "Specificite culturelle sud-asiatique + watermark. Geste tendre tres mignon (un homme qui dessine sur la main de sa partenaire). Mais inutilisable telle quelle (droits, watermark). A garder en reference pour inspirer une scene 'gestes du quotidien d'un couple'."
        ),
        "emotions": ["tenderness", "complicity", "playful"],
        "ambiance": ["intimate", "playful", "warm"],
        "setting": ["indoor", "home"],
        "colors": ["green_lime", "warm"],
        "style_tags": ["pinterest_aesthetic", "pov", "watermarked"],
        "cultural_specificity": "south_asian",
        "has_text_overlay": True,
        "text_content": "@amweirdoo",
        "quality_score": 6,
        "composition": "close_up",
        "compaatible_fit": "low",
        "suggested_avatars": [],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Watermark Pinterest @amweirdoo visible. Specificite culturelle. Ne pas reutiliser commercialement.",
        "notes": "Reference d'idee, pas d'asset.",
    },
    {
        "filename": "013ef85482310a6f50593f8fb46fe487.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo de dos d'un couple regardant un coucher de soleil dramatique au-dessus d'un lac ou d'une riviere. La femme (longs cheveux noirs, chale a motifs stars Louis Vuitton style) a la tete posee sur l'epaule de l'homme (chemise bleu pale). Ciel charge, nuages epais, un arc-en-ciel discret. Ton sombre, presque crepusculaire. Reflets sur l'eau."
        ),
        "marketing_use": (
            "Tres haute valeur. Pas de visages = libre. L'image incarne 'le couple installe qui partage un silence'. Forte resonance avec le Master KB (Idealiste 6, Lucide 1) : 'le silence a deux est le plus haut signe de compatibilite'."
        ),
        "emotions": ["intimacy", "calme", "tendresse", "wonder"],
        "ambiance": ["sunset", "moody", "cinematic", "dark"],
        "setting": ["outdoor", "lake", "nature"],
        "colors": ["dark", "muted", "warm_accent", "blue"],
        "style_tags": ["pinterest_aesthetic", "from_behind", "moody"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "from_behind",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 1, 5, 9],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Palette tres compatible avec le ton de marque.",
    },
    {
        "filename": "0141c426ce7749090f8f322485a6dd50.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo couple dans une cuisine rustique italienne ou espagnole : enduit blanc cassé, vieille cuisiniere creme retro, etagere en bois avec tasses et theiere rouge, applique murale industrielle. La femme (longs cheveux bruns mouilles, grande chemise rayee blanche aux cuisses nues) est dans les bras de l'homme (sweat gris fonce, pantalon raye creme, pieds nus). Etreinte intime du matin, vue de cote/dos. Ambiance 'lendemain de matin slow life'."
        ),
        "marketing_use": (
            "Reference parfaite du 'cozy intime quotidien' qu'on cherche pour Compaatible. Convient avatars 5, 6, 7, 9 (la vie de couple installee qu'on imagine). Plus realiste que les images sunsets : c'est l'intimite du dimanche matin."
        ),
        "emotions": ["intimacy", "calme", "softness", "domestic_love"],
        "ambiance": ["cozy", "morning", "slow_life", "intimate"],
        "setting": ["indoor", "kitchen", "home"],
        "colors": ["warm", "cream", "muted", "earth"],
        "style_tags": ["lifestyle_real", "pinterest_aesthetic", "slow_living"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "mid_shot",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 7, 9, 11],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Image iconique slow-life couple. Tres reutilisable.",
    },
    {
        "filename": "0167e7b2531066c3de61588ee695874c.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo nocturne d'un couple qui s'enlace au milieu d'un parking ou d'une cour, sous une pluie battante. Lampadaire au loin. Vetements sombres. Plan large, ambiance noir et grise, presque cinematique a la Wong Kar-wai. Tres melancolique."
        ),
        "marketing_use": (
            "Excellente pour illustrer 'l'amour malgre tout' ou 'se retrouver dans le chaos'. Convient avatars 6 (Idealiste, poesie cinematique), 9 (Separee qui retrouve quelqu'un), 4 (Guerriere : on s'en fout des conditions, on est ensemble)."
        ),
        "emotions": ["intimacy", "passion", "melancholy", "drama_doux"],
        "ambiance": ["rainy", "nighttime", "cinematic", "moody"],
        "setting": ["outdoor", "urban", "night", "rain"],
        "colors": ["dark", "grey", "blue", "muted"],
        "style_tags": ["cinematic", "moody", "lifestyle_real"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "wide",
        "compaatible_fit": "high",
        "suggested_avatars": [6, 9, 4, 7],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. Tres cinematique.",
    },
    {
        "filename": "017dc561c79748b63448e4f60c88987e.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo editoriale d'un couple au pied d'un escalier en pierre devant un chateau ou manoir. La femme en grande robe jaune princesse fluide, longs cheveux blonds, regard tourne vers l'homme. L'homme en chemise blanche simple, pantalon noir, mains dans les poches. Lanterne ancienne fixee au mur. Pelouse en arriere-plan, lumiere doree fin d'apres-midi. Ambiance conte de fees realiste, photographie de mariage haut de gamme."
        ),
        "marketing_use": (
            "Convient l'avatar 6 (Idealiste Reveuse, conte de fees) mais avec prudence : la robe est tres 'wedding' donc plus engagement que matching. A utiliser comme symbole de 'la prochaine etape ideale' plutot que rencontre. Aussi 3 (Curieuse de soi : 'quel type es-tu en amour ?')."
        ),
        "emotions": ["romance", "wonder", "elegance", "rever"],
        "ambiance": ["dreamy", "fairy_tale", "golden_hour", "cinematic"],
        "setting": ["outdoor", "castle", "garden"],
        "colors": ["warm", "amber", "yellow", "stone"],
        "style_tags": ["editorial_photography", "wedding_aesthetic", "cinematic"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "wide",
        "compaatible_fit": "medium",
        "suggested_avatars": [6, 3, 9],
        "suggested_platforms": ["instagram", "reddit"],
        "usage_warning": "Robe princesse + chateau = registre 'mariage' qui pourrait dissoner avec le pre-engagement Compaatible.",
        "notes": "Format portrait. Tres beau visuel.",
    },
    {
        "filename": "0197989287683009bd9a98bf06daa522.jpg",
        "image_type": "photo_real",
        "subject_type": "object_scene",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Photo noir et blanc d'un ecran de MacBook ouvert sur un appel video. A l'ecran : la jeune femme blonde a l'autre bout sourit ; au premier plan, deux mains (l'une depuis l'ecran/l'autre depuis l'utilisateur) forment ensemble un coeur. Le clavier visible en bas, chambre en desordre en haut (chaussures, vetements). Ambiance distance-relationship/college dorm."
        ),
        "marketing_use": (
            "Concept fort pour Compaatible : 'le coeur se forme avant qu'on se touche'. Pour avatars 6 et 7. MAIS : photo perso avec visage identifiable + B&W qui dissone du ton warm Compaatible. Utiliser pour un thread sur la longue distance / le matching pre-rdv mais pas en visuel principal."
        ),
        "emotions": ["longing", "tenderness", "youth_love"],
        "ambiance": ["intimate", "nostalgic", "youth"],
        "setting": ["indoor", "bedroom", "screen"],
        "colors": ["black_white", "monochrome"],
        "style_tags": ["lifestyle_real", "black_white", "pov"],
        "cultural_specificity": "western",
        "has_text_overlay": False,
        "quality_score": 7,
        "composition": "pov",
        "compaatible_fit": "medium",
        "suggested_avatars": [7, 6, 3],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Visage identifiable de tiers, droits a verifier. B&W casse le ton chaleureux.",
        "notes": "Bon concept, format pas ideal.",
    },
    {
        "filename": "01b12bb57fe8dd1b119899cd5174e6c7.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": False,
        "description": (
            "Photo close-up d'un couple en chemises blanches a fines rayures bleues/grises. L'homme (barbu, cheveux fonces) embrasse la tete de la femme (longs cheveux bruns ondules). Sa main repose tendrement sur le ventre / cuisse de la femme, jean visible. Cadrage tres serre buste. Lumiere naturelle douce. Look casual chic."
        ),
        "marketing_use": (
            "Image versatile : couple visiblement complice, pas de visages, geste tendre. Le matching tenue (chemises rayees) suggere la 'compatibilite stylistique' subtile. Avatars 5, 6, 7, 9."
        ),
        "emotions": ["tenderness", "complicity", "calme", "love"],
        "ambiance": ["soft", "intimate", "casual_chic"],
        "setting": ["indoor", "neutral"],
        "colors": ["muted", "blue_pale", "white", "warm"],
        "style_tags": ["lifestyle_real", "close_up", "pinterest_aesthetic"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 8,
        "composition": "close_up",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 7, 9],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format paysage. Tres reutilisable.",
    },
    {
        "filename": "01c3ff8221b172f049151dd01d374189.png",
        "image_type": "photo_real",
        "subject_type": "single_person",
        "people_count": 1,
        "faces_visible": False,
        "description": (
            "Photo de dos d'une jeune femme blonde assise sur des rochers au bord de la mer au coucher du soleil. Robe noire longue dos nu a fines bretelles croisees. Mer calme rose pastel, ciel rose-mauve degrade. Cadrage portrait vertical. Tres aesthetic Pinterest."
        ),
        "marketing_use": (
            "Femme seule contemplative au crepuscule = parfait pour avatar 5 (Introverti), 6 (Idealiste), 9 (Separee). Pas de drama, ton doux. Excellente palette warm complementaire."
        ),
        "emotions": ["solitude", "elegance", "contemplation", "melancholy_douce"],
        "ambiance": ["sunset", "soft", "dreamy", "calme"],
        "setting": ["outdoor", "beach", "rocks", "sea"],
        "colors": ["pastel", "pink", "black", "muted"],
        "style_tags": ["pinterest_aesthetic", "from_behind", "lifestyle_aesthetic"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 9,
        "composition": "from_behind",
        "compaatible_fit": "high",
        "suggested_avatars": [5, 6, 9],
        "suggested_platforms": ["twitter", "reddit", "instagram"],
        "usage_warning": None,
        "notes": "Format portrait. PNG. Tres haute valeur.",
    },
    {
        "filename": "01c435ed1c2d12824abf6c67e8db1937.jpg",
        "image_type": "photo_real",
        "subject_type": "couple",
        "people_count": 2,
        "faces_visible": True,
        "description": (
            "Photo noir et blanc d'un couple selfie miroir dans une salle de musculation. La femme en brassiere blanche et leggings noir, l'homme en t-shirt et short noirs, casquette. Tous deux contractent les biceps pour la photo. Cordes a sauter par terre, racks de poids, kettlebells. Ambiance fitness couple."
        ),
        "marketing_use": (
            "OFF_BRAND ou tres LOW pour Compaatible : le fitness couple est une niche specifique qui n'est pas le territoire Compaatible (qui parle de compatibilite psychologique, pas physique). Plus 'workout buddies' que 'ame soeur'."
        ),
        "emotions": ["energy", "complicity", "playful"],
        "ambiance": ["sporty", "energetic"],
        "setting": ["indoor", "gym"],
        "colors": ["black_white", "monochrome"],
        "style_tags": ["lifestyle_real", "gym_couple", "mirror_selfie"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 6,
        "composition": "wide",
        "compaatible_fit": "low",
        "suggested_avatars": [],
        "suggested_platforms": ["organic_only"],
        "usage_warning": "Visages identifiables. Niche fitness pas alignee Compaatible.",
        "notes": "Photo perso tiers, pas un asset.",
    },
    {
        "filename": "01f282f0f8d155a3f5247cab66a35885.jpg",
        "image_type": "photo_real",
        "subject_type": "object_scene",
        "people_count": 0,
        "faces_visible": False,
        "description": (
            "Photo de salon de yacht luxe decore pour un anniversaire : des dizaines de ballons roses pales et blancs flottent au plafond, ceintures roses pendant. Sur une table ronde, un grand bocal en verre contenant un bouquet de roses pales et une etiquette 'Happy Birthday'. Canapes blancs avec coussins motifs noir/blanc. Boiseries chaudes, fenetres avec vue mer. Setup decoration luxueuse."
        ),
        "marketing_use": (
            "OFF_BRAND : luxe ostentatoire (yacht) + setup tres 'fete privee influenceuse'. Aucun rapport avec la promesse Compaatible. A ignorer."
        ),
        "emotions": ["celebration", "luxury", "fete"],
        "ambiance": ["luxury", "celebration", "feminine"],
        "setting": ["indoor", "yacht"],
        "colors": ["pink_pastel", "white", "wood"],
        "style_tags": ["luxury_setup", "balloons", "instagram_flex"],
        "cultural_specificity": "universal",
        "has_text_overlay": False,
        "quality_score": 6,
        "composition": "wide",
        "compaatible_fit": "off_brand",
        "suggested_avatars": [],
        "suggested_platforms": [],
        "usage_warning": "Luxe ostentatoire. A ignorer.",
        "notes": "Off-topic.",
    },
]


def main() -> None:
    for i, meta in enumerate(BATCH, 1):
        new_id = insert_image(meta)
        print(f"[{i}/{len(BATCH)}] id={new_id} fit={meta['compaatible_fit']:10s} avatars={meta['suggested_avatars']}")
    print(f"\nBatch 003: {len(BATCH)} inserted.")


if __name__ == "__main__":
    main()
