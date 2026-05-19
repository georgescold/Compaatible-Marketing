# CLAUDE.md — Compaatible

> Ce fichier est la mémoire vivante du projet. Chaque erreur corrigée, chaque décision prise, chaque règle apprise doit être ajoutée ici. Après chaque correction : **"Mets à jour CLAUDE.md pour ne plus commettre cette erreur."**

---

## 🧠 Contexte du projet

**Compaatible** est une app de rencontres basée sur la psychologie des Big Five (OCEAN) ciblant le marché français avec ambitions internationales. L'idée centrale : matcher les utilisateurs selon leur compatibilité de personnalité mesurée scientifiquement, pas selon leurs photos.

**Fondateur** : Loys (micro-entrepreneur francais)  
**Stade** : Early-stage, pre-launch  
**Marche principal** : France → International  
**Produit** : App mobile (Expo/React Native) = le produit. Site web (Vue 3) = acquisition.  
**Stack** : Vue 3 + AdonisJS + Supabase + Expo + Vercel + Railway  
**Domaine** : compaatible.com  
**Analytics** : PostHog  
**Paiement** : IAP Apple/Google via RevenueCat (app mobile, abonnement 9,99€/session). Rapport couple site web : statut Stripe à confirmer.

---

## 🏗️ Architecture technique

### Stack complete
```
App mobile     → Expo (React Native), TypeScript, NativeWind, Zustand
Site web       → Vue 3 (Composition API), TypeScript, Vite, Tailwind CSS
Backend        → AdonisJS v6, Lucid ORM, TypeScript
Admin panel    → React, TypeScript, Vite, Tailwind CSS
Base de donnees → Supabase (PostgreSQL)
Hebergement    → Vercel (site + admin) + Railway (backend)
Email (transac + marketing) → Resend (domaine send.compaatible.com) + Amazon SES
DNS            → OVH (nameservers) → Vercel (A/CNAME) + Zoho Mail (MX)
Analytics      → PostHog
Paiement       → IAP Apple/Google via RevenueCat (mobile, abonnement 9,99€/session). Site web rapport couple : Stripe (à confirmer)
SEO/Blog       → Articles generes via n8n + Supabase
```

### Funnel de conversion
```
SITE : pageview → cta_clicked → test_started → test_completed → app_redirect
APP  : app_open → login → reveal_viewed → session_joined → match_unlocked → payment
```

### Structure des tables Supabase (principales)
- `users` — donnees utilisateur + Big Five + tier + promo + RGPD (`cgu_accepted_at`, `marketing_opt_in_at`, `review_validated_at`, `pending_unlock_compensation`)
- `test_results` — reponses au test + scores + type de personnalite
- `sessions` / `session_participants` — sessions de matching mensuelles (le 1er et le 15)
- `matches` — paires de compatibilite calculees + deblocages + colonnes connexion (`connection_status`, `connection_initiated_by`, `connection_request_at`, `connection_resolved_at`, `connection_refused_reason`, `connection_auto_unlocked_at`, etc.)
- `messages` — chat 1-1 entre matchs (avec messages systeme `type='system'` pour les interventions bot narrateur)
- `feedback_conversations` — bot Compaatible (collecte feedback fin de session, bonus story/avis, charter_accepted, story_bonus_claimed, testimonial_consent)
- `support_tickets` — tickets support multi-sources (`source: app | email | form | manual`)
- `couples` / `couple_invitations` / `couple_reports` — funnel couple site web (rapport 4,99€)
- `articles` — blog SEO genere automatiquement (pipeline n8n)
- `site_settings` — config dynamique (bandeau, promo, countdown)
- `page_visits` — tracking visites (IP, geo, ref_tag)
- `blacklist` / `user_blocks` — personnes a eviter en matching (base legale = interet legitime RGPD)

---

## 🧬 Modele Big Five & 16 types de personnalite (coeur produit)

> Le cœur conceptuel de Compaatible. Tout le matching, tout le copywriting, tout le design produit s'appuie sur ce modele. **Comprendre cette section avant de toucher au produit.**

### Le Big Five (OCEAN) — fondement scientifique

Compaatible utilise le **modele Big Five** (ou OCEAN), le modele de personnalite le plus valide scientifiquement (60 ans de recherche, consensus academique). Contrairement au MBTI (16Personalities) ou aux quiz maison de la concurrence, le Big Five mesure 5 dimensions stables et orthogonales sur un continuum 0-100.

| Lettre | Dimension | Mesure | Pole + | Pole - |
|--------|-----------|--------|--------|--------|
| **O** | Openness (Ouverture) | Curiosite intellectuelle, gout du nouveau, imagination | Cherche le neuf, l'art, les idees | Aime la routine, le familier |
| **C** | Conscientiousness (Conscience) | Organisation, discipline, fiabilite | **Structure** : planifie, tient ses engagements | **Libre** : spontane, flexible |
| **E** | Extraversion | Energie sociale, recherche de stimulation | Energique, sociable, expressif | Reflechi, calme, reserve |
| **A** | Agreeableness (Agreabilite) | Cooperation, empathie, harmonie | **Chaleureux** : empathique, accommodant | **Affirme** : direct, competitif |
| **N** | Neuroticism (Nevrosisme) | Sensibilite emotionnelle, gestion du stress | **Intense** : ressent fort, reactif | **Serein** : stable, calme sous pression |

**Test mobile** : 90 questions, ~15 min, 30 facettes (6 par domaine), scores normalises 0-100. Stockes dans `test_results.scores`. Sources : `apps/mobile/data/bigfive-questions.ts` + `apps/backend/app/services/compatibility_scoring.ts`.

### Les 4 familles de personnalite (regroupement par 2 axes)

Les 16 types sont organises en **4 familles** definies par 2 axes : la **Conscience** (Structure vs Libre) et l'**Agreabilite** (Affirme vs Chaleureux). Chaque famille a une couleur, un logo SVG et une signature emotionnelle.

| Famille | Code axes | Couleur | Signature | Subtitle UI |
|---------|-----------|---------|-----------|-------------|
| **Architectes du Cœur** | Structure + Affirme (S + A) | `#7B5EA7` (violet) | Vision, ambition, exigence | "Structure + Affirme" |
| **Gardiens du Lien** | Structure + Chaleureux (S + C) | `#4A857E` (teal) | Loyaute, fiabilite, soin du quotidien | "Structure + Chaleureux" |
| **Ames Lumineuses** | Libre + Chaleureux (L + C) | `#5E8A72` (vert sauge) | Empathie, douceur, profondeur emotionnelle | "Libre + Chaleureux" |
| **Flammes Libres** | Libre + Affirme (L + A, "Audacieux") | `#B8783D` (ambre) | Liberte, audace, intensite | "Libre + Audacieux" |

Source : `apps/mobile/data/personality-types.ts` + `apps/frontend/src/data/personality-types.ts`.

### Les codes a 4 lettres (encodage IASS, ICLS, etc.)

Chaque type a un **code de 4 lettres** qui encode son profil OCEAN (les axes E, A, C, N — l'Ouverture O n'est pas utilisee dans le code).

| Position | Axe | Lettres |
|----------|-----|---------|
| 1 | **Extraversion** | `I` (Introverted) / `E` (Extraverted) |
| 2 | **Agreabilite** | `A` (Affirme) / `C` (Chaleureux) |
| 3 | **Conscience** | `S` (Structure) / `L` (Libre) |
| 4 | **Nevrosisme** | `S` (Serein) / `I` (Intense) |

Exemple : `IASS` = Introverti + Affirme + Structure + Serein = **Le Stratege Serein** (famille Architectes).

### Les 16 types de personnalite (ordre entrelace par famille)

Les types sont stockes dans un ordre **entrelace** pour le carousel d'onboarding (1 par famille en rotation, evite que 2 types de la meme famille se suivent).

#### 🏛️ Architectes du Cœur (Structure + Affirme)
| Code | Nom | Essence |
|------|-----|---------|
| `IASS` | **Le Stratege Serein** | Calme et reflechi, choisit apres mure reflexion, loyaute totale, vise le long terme |
| `IASI` | **Le Sculpteur Passionne** | Intense et exigeant, profondeur rare, attend la meme rigueur, relation sincere alignee sur ses valeurs |
| `EASS` | **Le Commandant Bienveillant** | Charismatique et stable, prend les renes en protegeant, engagement total |
| `EASI` | **L'Etoile Magnetique** | Charismatique et intense, vit l'amour avec passion totale, presence marquante |

#### 🛡️ Gardiens du Lien (Structure + Chaleureux)
| Code | Nom | Essence |
|------|-----|---------|
| `ICSS` | **Le Protecteur Fidele** | Attentionne et fiable, gestes du quotidien, n'oublie aucun detail, stabilite |
| `ICSI` | **Le Guerisseur Tendre** | Empathique et patient, accueille les blessures, espace de reconfort, parfois s'oublie |
| `ECSS` | **Le Pilier Rayonnant** | Solide et genereux, fiable en toutes circonstances, presence rassurante + chaleur sincere |
| `ECSI` | **Le Cœur Volcanique** | Fiable mais bouillonnant, stabilite + intensite emotionnelle rare, aime sans demi-mesure |

#### ✨ Ames Lumineuses (Libre + Chaleureux)
| Code | Nom | Essence |
|------|-----|---------|
| `ICLS` | **Le Sage Bienveillant** | Doux et patient, presence apaisante, ecoute sans juger, relation paisible et profonde |
| `ICLI` | **Le Reveur Romantique** | Idealiste et devoue, reve d'amour absolu, investit toute son ame, sensibilite + vulnerabilite |
| `ECLS` | **Le Mentor Solaire** | Chaleureux et inspirant, pousse l'autre a grandir, couple comme espace de croissance mutuelle |
| `ECLI` | **Le Papillon Empathique** | Curieux et enthousiaste, se connecte facilement, magie dans chaque rencontre, terrain de jeu |

#### 🔥 Flammes Libres (Libre + Audacieux)
| Code | Nom | Essence |
|------|-----|---------|
| `IALS` | **L'Artisan du Moment** | Pragmatique et independant, actes concrets > grands discours, besoin d'espace, respecte la liberte |
| `IALI` | **L'Artiste Spontane** | Creatif et instinctif, refuse les conventions, invente sa facon d'aimer, rythme imprevisible |
| `EALS` | **L'Aventurier Audacieux** | Energique et audacieux, vie de couple = aventure permanente, fuit la routine |
| `EALI` | **La Comete Flamboyante** | Imprevisible et eblouissante, amour = feu d'artifice, refuse qu'on l'eteigne |

### Algorithme de matching (composition du score 0-100)

Source : `apps/backend/app/services/compatibility_scoring.ts::computeCompatibilityScore`.

**Score final = 85% Big Five + 10% hobbies communs + 5% alignement partenaire ideal**

#### 1. Big Five score (85% du total) — la composante principale

Ponderation par dimension (somme = 100%) :

| Dimension | Poids | Justification |
|-----------|-------|---------------|
| **N (Stabilite emotionnelle)** | **30%** | Critere n°1 pour la longevite d'un couple. Deux N eleves = friction chronique. |
| **A (Agreabilite)** | **25%** | Similarite = harmonie quotidienne (cooperation vs competition). |
| **C (Conscience)** | **20%** | Similarite = organisation de vie commune (rythme, fiabilite). |
| **E (Extraversion)** | **15%** | **Complementarite enrichissante** : on penalise 2x moins la difference (`similarity = 100 - |diff| * 0.5`). Un introverti + un extraverti fonctionne bien. |
| **O (Ouverture)** | **10%** | Divergence toleree. Pas critique pour le couple. |

**Penalite double instabilite N** : si moyenne (N_a + N_b) / 2 > 60, on retire `(avgN - 60) * 0.8` au score de la dimension N. Deux personnes emotionnellement instables ensemble = drama chronique.

Reference scientifique : Donnellan, Conger & Bryant, **"The Big Five and enduring marriages"**, Journal of Research in Personality, 2004.

#### 2. Hobbies score (10% du total)

Indice de **Jaccard** sur les ensembles d'interets : `|intersection| / |union| * 100`. Mesure la similarite des hobbies declares.

#### 3. Trait alignment / partenaire ideal (5% du total)

Indice de Jaccard sur les **traits recherches chez l'autre**. Logique : si A et B cherchent les memes qualites chez leur partenaire, leurs valeurs sont alignees → meilleure harmonie. C'est le bonus "green flags".

#### 4. Jitter deterministe (anti-egalite)

`applyPairJitter()` ajoute un micro-jitter `[-0.4, +0.4]` base sur le hash des 2 user IDs. Stable (memes IDs = meme jitter). Permet de differencier des paires qui auraient sinon le meme score arrondi.

#### 5. Compatibilite des types (TYPE_COMPAT) — usage decoratif

Pour chaque type, on a 3 listes : `best` (100), `good` (70), `challenging` (20). **Cette table N'est PAS dans le score final** (fonction `typeScore` existe mais n'est plus appelee dans `computeCompatibilityScore`). Elle sert au **breakdown narratif** des cartes match et au copy "Pourquoi ca matche".

### Breakdown OCEAN du match (cote mobile)

`apps/mobile/components/CompatibilityBreakdown.tsx` + `services/compatibility_scoring.ts::computeMatchBreakdown`.

Pour chaque dimension OCEAN, on classe l'alignement en 3 categories :

| Classification | Critere | Couleur UI | Signification |
|----------------|---------|------------|---------------|
| **Aligned** (Alignes) | `|diff| < 20` | Vert | Vous fonctionnez pareil sur cette dimension |
| **Complementary** (Complementaires) | `20 ≤ |diff| < 40` (sur E surtout) | Burgundy | Vos differences se renforcent mutuellement |
| **Contrast** (A nuancer) | `|diff| ≥ 40` | Orange | Friction potentielle, a discuter |

Insights texte stocks dans `BREAKDOWN_INSIGHTS` (banque de phrases par dimension × alignement). **Premium voit les insights / Decouverte voit la structure mais insights caches** (CTA paywall).

### Familles compatibles entre elles (regle empirique)

Au-dela du score numerique, certaines paires de familles fonctionnent particulierement bien :

- **Architectes ↔ Ames** : la rigueur rencontre la douceur, complementarite emotionnelle
- **Gardiens ↔ Flammes** : la stabilite donne un cadre a la liberte, equilibre yin/yang
- **Architectes ↔ Gardiens** : 2 structures, valeurs partagees, complicite de fond
- **Ames ↔ Flammes** : 2 esprits libres, romantisme + audace
- **Architectes ↔ Flammes** : friction possible (rigueur vs spontaneite), passion intense si ca passe
- **Gardiens ↔ Ames** : 2 chaleureux, douceur permanente, peut manquer de challenge

Ces regles narratives alimentent le copy in-app (modal de refus, breakdown, etc.). Elles ne sont pas codees dans le score, c'est de la **psychologie produit** pour rendre les insights humains.

### Pourquoi cette approche differencie Compaatible

| Concurrent | Methode | Probleme |
|------------|---------|----------|
| Tinder/Bumble/Hinge | Swipe sur photos | Apparence > compatibilite, fatigue de swipe |
| Yoyomatch | Quiz maison non valide | Questions changeantes, base scientifique nulle |
| Meetic/Adopte | Filtres demographiques | Age + ville + interets de surface |
| MBTI (16Personalities) | 4 axes binaires | Pas predictif (categories trop tranchees, scientifiquement conteste) |
| **Compaatible** | **Big Five OCEAN, 30 facettes, scoring pondere** | **Mesure stable, predictive, 60 ans de recherche** |

Le marketing pre-inscription peut parler de "science" et "Big Five" (cf. `Compaatible-skills-main/context.md`). **L'app post-onboarding NE doit JAMAIS** dire "science" ou "scientifique" (decision Loys, voir `feedback_pas_de_science.md`). En interne on parle de "methode", "approche", "systeme de matching".

---

## 🚀 Fonctionnalites & parcours utilisateur

> Cette section decrit l'experience utilisateur reelle de Compaatible : comment un utilisateur passe du landing site web a une session de matching aboutie dans l'app mobile.

### Vue d'ensemble du parcours

```
SITE WEB (acquisition)
  Landing → test Big Five gratuit (90 questions) → reveal categorie/famille → CTA app mobile
  (Couples : meme test → invitation partenaire → rapport couple 4,99€ sur le site)

APP MOBILE (produit)
  Telechargement → onboarding 2 phases → inscription → test (si pas fait sur le site)
  → Espace Compaatible (Home) → inscription session → test de session
  → Reveal ceremonie (annonce des compatibilites) → cartes compatibilites
  → Demande de connexion explicite → accept/refuse → chat (fenetre 4j ou 7j)
  → Cloture session + bilan + bot feedback (chips presets + bonus story/avis)
  → Session suivante (le 1er ou le 15 du mois)
```

### Onboarding mobile (2 phases distinctes)

`apps/mobile/app/onboarding/index.tsx` + 10 sous-etapes (age-preference, notifications, location, photos, gender, premium, auth, profile, complete).

- **Phase 1 "soul" (welcome)** : 6 personas (Sophie, Marc, Camille, Thomas, Lea, Antoine) qui defilent en single card centree avec auto-advance 3500ms. Medaille % en overlap. Ne PAS fusionner avec phase 2.
- **Phase 2 "cards" (decouverte)** : carousel coverflow infini des 16 personnalites (PersonalityCard, INFINITE_CYCLES=9). Decouverte volontaire du systeme Big Five.

### Test Big Five (90 questions, 15 min)

- 90 questions, 30 facettes, 5 domaines OCEAN → 16 types de personnalite repartis en 4 familles (Architectes, Ames, Gardiens, Flammes).
- Disponible site web (`apps/frontend/src/views/TestView.vue`) ET app mobile (`apps/mobile/app/test/`). Resultat sync via `test_results`.
- Sur le site, le user choisit AVANT le test sa situation amoureuse (celibataire / couple). Les couples sautent partenaire ideal + photo.

### Espace Compaatible (Home tab post-onboarding)

`apps/mobile/app/(tabs)/index.tsx` — l'ecran principal du produit.

- Header eyebrow "ESPACE COMPAATIBLE" + titre permanent "{Prenom}, c'est ici que tout commence."
- `SessionCard` : bandeau session courante avec sous-titres aleatoires stables par session.id ("Les des sont lances.", etc.)
- Avatars participants : 5 SVG personnalites floutees defilant doucement (LinearTransition 8s). Reflete les vrais inscrits via `session.participantPersonalityIds`.
- Countdown jusqu'a la reveal ("Annonce des compatibilites" — ne JAMAIS dire "Revelation").
- `FomoPlanModal` propose l'upgrade Decouverte → Experience avant le `CycleRegistrationModal` (inscription session).

### Sessions mensuelles (1er et 15)

- Backend : `apps/backend/app/services/session_scheduler.ts` + `matching_service.ts`.
- 2 sessions par mois (1er et 15). User inscrit doit passer un test de session court (`CycleRegistrationModal`, 20 questions + disclaimer "engagement").
- Si test pas passe a temps → crédit reporte : la session suivante est **gratuite** (pas de re-prelevement IAP).
- Reveal = annonce des compatibilites a date fixe. C'est la "ceremonie" centrale du produit.

### Cartes compatibilites + Match Detail + Breakdown OCEAN

`apps/mobile/app/match/[id].tsx` + `apps/mobile/components/CompatibilityBreakdown.tsx`.

- Cartes verrouillees au reveal → user deverrouille selon ses limites (`computeUnlockLimits`).
- Decouverte : 1 deblocage base / Experience : 8 deblocages base (voir Systeme de bonus ci-dessous).
- Section "POURQUOI CA MATCHE" : 5 dimensions OCEAN avec barres comparatives, badges Alignes/Complementaires/A nuancer, insights texte.
- Premium voit les insights / Decouverte voit la structure mais insights caches + CTA paywall.
- Carte profil format obligatoire : photo + nom/age + ville + pill perso + customTagline + hobbies emoji.

### Systeme de demande de connexion explicite (bilateral, 48h)

`apps/mobile/app/connection-request/[id].tsx` + contrat `apps/backend/CONNECTION_REQUEST_CONTRACT.md`.

- **Remplace le chat ouvert par defaut** : chaque conversation est un choix mutuel.
- Bilateral : si les 2 initient independamment → auto-match (transaction FOR UPDATE backend).
- Expire a 48h sans reponse → status `expired`. Job background `expiration-connexions` (cron horaire).
- 4 raisons de refus predefinies (anonymes cote partenaire) : `profile_not_resonating`, `no_compatibility_felt`, `wrong_timing`, `prefer_not_to_say`.
- Modal de refus : disclaimer culpabilisant (5 variants personnalises par hash prenom + score + famille + hobbies) + picker raison.
- Vocabulaire : "Connexion" (pas "Demande") dans le copy in-app. **"Debloquer"** = action mecanique vs **"Decouvrir"** = exploration profil.
- Auto-unlock cote B : si A initie sur un match dont B n'a pas encore unlocked, backend auto-unlock cote B sans decrementer son quota. Animation `/connection-arriving/` avant `/connection-request/`.
- Refused vs expired : copy different. Refused = "{Prenom} n'a pas donne suite." + ton empathique. Expired = "{Prenom} n'a donne aucun signe de vie..." + message anti-ghosting.

### Compensation refus en serie (cas extreme)

- Trigger : 3+ connexions initiees toutes en refused/expired, aucune accepted, rolling 30j, pas deja compense sur 90j.
- Mecanique : code promo personnel 100% sur plan Experience, valable 60 jours. Stocke sur `users.promo_code` + flag `users.pending_unlock_compensation`.
- Compaatible **assume la faute** ("on a surement fait erreur dans nos calculs"). Push opaque "Un message t'attend" + message bot dans `feedback_conversation` avec le code promo.
- Job backend hebdomadaire qui detecte + grant. User n'a rien a demander.

### Fenetre chat 4j / 7j

`apps/backend/app/services/chat_window.ts`.

- **4 jours** si Decouverte ↔ Decouverte.
- **7 jours** si au moins un Experience dans la paire (plafond 7j depuis `session.reveal_date`).
- Backend enforce expiration sur `POST /api/matches/:id/messages` → 403 si fermee.
- Mobile expose `chatWindowDays: 4 | 7` dans `/api/me` sans exposer `partner.tier` (utilise dans copy adaptatif modal de refus).
- Chat ouvert a tous les tiers (Decouverte aussi peut chatter). Ne pas gater le chat derriere Premium.

### Bot Compaatible (chat feedback fin de session)

`apps/backend/app/controllers/feedback_controller.ts` + `apps/mobile/app/chat/[id].tsx` (FeedbackChatScreen).

- 4 states calcules backend qui pilotent l'input mobile :
  - `free_feedback` (default) : chips 4 categories (Plu / A ameliorer / Idee / Bug) + bottom sheet multi-select + CTA "Terminer mon retour".
  - `bonus_pending` : camera CTA principal, l'user doit envoyer un screenshot story/avis.
  - `bonus_under_review` : banniere "On verifie ton screenshot sous 24h", aucun input.
  - `feedback_done` : banniere "Ton retour est enregistre", aucun input.
- **Le bot ne repond JAMAIS aux questions ouvertes**. Quick reply "Poser une question a l'equipe" → redirige vers `/support` (entonnoir FAQ).
- Relance bonus : push J+2 si bonus story/avis non reclame (Decouverte uniquement). Push opaque "Nouveau message".
- Consent publication temoignage stocke a la fin du flow (RGPD : conservation de la preuve).

### Systeme de bonus deblocages (story Insta/FB + avis store)

`apps/backend/app/controllers/matches_controller.ts::computeUnlockLimits`.

| | Decouverte | Experience |
|---|----------|------------|
| Base session | 1 | 8 |
| Bonus avis store (a vie) | +1 a vie | +2 a vie |
| Bonus story Insta/FB (par session) | +1 recurrent | ❌ non disponible |
| Max session | 3 | 10 |

- **Avis = a vie une seule fois** (`users.review_validated_at`). Une fois set, jamais reproposé.
- **Story = par session** (`feedback_conversations.story_bonus_claimed`), recurrente, **Decouverte uniquement** (les payants ne sont pas sollicites pour promouvoir).
- Validation admin via `admin_controller` (`validateBonus`, `activateStoryBonus`, `approveScreenshot`).

### Paywall IAP (RevenueCat, mobile)

`apps/mobile/app/paywall/index.tsx` + `apps/mobile/lib/purchases.ts`.

- Plan unique : **abonnement 9,99€ par session**. Pas de Stripe sur mobile (rejet App Store / Play Store).
- Naming UI : **Decouverte** (gratuit) / **Experience** (paye). Variables code intactes (`tier='free'|'premium'`).
- Cycle IAP technique encore a trancher (subscription mensuelle pilotee backend / consumables / weekly) — Apple ne supporte pas "tous les 15 jours" nativement.
- Crédit reporte explique sur le paywall : session loupee = session suivante gratuite.

### Support en entonnoir FAQ (7 categories)

`apps/mobile/app/support.tsx`.

- 4 etapes : Categories → Questions FAQ pre-redigees → Reponse inline + CTA "Oui, merci" ou "Non, contacter l'equipe" → Formulaire avec categorie + sujet pre-remplis.
- 7 categories : `bug`, `account`, `payment`, `match`, `bonus`, `session`, `other`.
- Liste des tickets envoyes affichee en bas (statut + reponse admin).
- Cote admin : `SupportPanel` (source='app') et `SavPanel` (source='email|form|manual' via Zoho/Tally).

### Notifications push (6 cron GitHub Actions)

`.github/workflows/push-notifications-cron.yml`.

- `session-lifecycle` (7h) : ouverture inscription, J-1 reveal, fin de session.
- `closing-ceremony` (8h12) : cloture session + bilan.
- `bot-bonus-48h` (9h23) : relance bonus story/avis non reclame (Decouverte).
- `test-incomplet` (10h47) : rappel test de session non passe.
- `validation-presence` (17h13) : anti-AFK pendant la fenetre chat.
- `expiration-connexions` (horaire) : passe les `pending > 48h` en `expired` + push aux initiateurs.

### Conformite RGPD (mai 2026)

- **Double consent au signup** : CGU obligatoire (`cgu_accepted_at`) + opt-in marketing FACULTATIF (`marketing_opt_in_at`, non pre-cocha).
- **Pas de marketing obligatoire** : Article 7.4 RGPD + jurisprudence Planet49. Tout envoi marketing DOIT passer par `sendMarketingEmail(to, subject, html)` qui skip silencieusement si pas d'opt-in.
- **Check age backend** : `auth_controller.register/googleRegister` + `users_controller.update` rejettent en 422 si age < 18.
- **Export RGPD** : `GET /api/me/export` retourne 3 blocs structures (meta + processing + data) incluant messagesSent ET messagesReceived. Article 15 + Article 20 RGPD.
- **Decision automatisee Art. 22** : section dediee dans pol. conf. (`ConfidentialiteView.vue` section 9) + FAQ mobile + export JSON. Decrit inputs/outputs, exclut donnees sensibles, liste les 3 droits user.
- **Delais de suppression** : desactivation immediate + suppression bases prod 30j + purge sauvegardes 6 mois + conservation legale (transactions) 10 ans. Aligne sur 4 surfaces (pol. conf., FAQ x2, export).
- **Brevo retire** (mai 2026) : Resend gere transactionnel ET marketing.

### Funnel couple site web (rapport 4,99€)

`apps/frontend/src/views/ResultatsView.vue` + `apps/frontend/src/views/ProfilView.vue`.

- L'initiateur passe le test couple → page invitation partenaire (token stocke `localStorage`, expire 48h).
- Le partenaire clique le lien → signup + test → rapport couple genere automatiquement.
- 2 espaces site web :
  - `/teaser` = celibataire (categorie/famille uniquement, CTA app mobile).
  - `/profil` = couple (3 etats : invitation / pending / reports). Type de personnalite revele dans le rapport.
- Site **ne fait PAS** de matching. Le matching = exclusivement dans l'app mobile.

---

## 🔑 Variables d'environnement critiques

```bash
# Ne JAMAIS hardcoder ces valeurs dans le code
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
RESEND_API_KEY=
POSTHOG_KEY=
EXPO_PUBLIC_REVENUECAT_IOS_KEY=
EXPO_PUBLIC_REVENUECAT_ANDROID_KEY=
# STRIPE_*= → uniquement si rapport couple site web reste sur Stripe (à confirmer)
```

**Règle** : Toutes les clés secrètes passent par `.env.local` (jamais committées) et les variables d'env Vercel pour la prod.

---

## 📣 Marketing & Copywriting — ADN profond de Compaatible

> Cette section consolide **tous les choix de copywriting** qui forgent l'identite de Compaatible. Tout texte visible par l'utilisateur (landing, CTA, emails, app, notifications, blog SEO) doit etre coherent avec ces regles. La source de verite externe est le dossier `Compaatible-skills-main/`. Cette section est la version condensee et operationnelle pour Claude.

### Le pari Compaatible (positionnement strategique)

Compaatible est **l'antithese** des apps de rencontre classiques. Tout le copy decoule de ce positionnement :

| Apps classiques (Tinder, Bumble, Hinge) | Compaatible |
|------------------------------------------|-------------|
| **Maximisent le temps passe** sur l'app (retention agressive) | **Veut que tu partes** (pari anti-retention) |
| Photos + swipe + scroll infini | Personnalite + matchs curates + cloture |
| Vocabulaire : "match", "swipe", "ghosting" | Vocabulaire : "compatibilite", "connexion", "decouvrir" |
| Vendent l'illimite | Vendent la qualite (jusqu'a 10 compatibilites/mois) |
| Gamification addictive | Ceremonie bimensuelle (le 1er et le 15) |
| Profils publics consultables | Profils invisibles jusqu'au match mutuel |

Ce positionnement n'est pas un argument marketing accessoire, c'est **l'ADN moral du produit**. Quand un user trouve l'amour, Compaatible lui dit "fonce et ne reviens plus jamais" (cf. regle anti-retention plus bas).

### Tagline et signature

- **Tagline officielle** : "Ton ame soeur existe. On va la trouver."
- **Signature anti-swipe** : "Ici, on ne swipe pas. On se comprend."
- **Signature CTA** : "Trouve l'amour, une bonne fois pour toutes."

### Distribution tonale 40/40/20

Tout texte Compaatible respecte cet equilibre :

- **40% Scientifique / Factuel** : Big Five, OCEAN, 5 domaines, 30 facettes, 60 ans de recherche, references academiques (Donnellan, Gottman, Helen Fisher).
- **40% Emotionnel / Romantique** : punchlines poetiques, connexion, "ame soeur", "se comprendre", "se reconnaitre".
- **20% Pratique / Rassurant** : FAQ, fonctionnement, garanties (anonymat, donnees confidentielles, no swipe).

**Archetype** : Romantique chaleureux + Premium luxe + Precision scientifique. Intelligent mais accessible. Structure mais pas clinique. Poetique mais ancre dans le reel. Assertif mais empathique.

### Vocabulaire signature (mots qui DEFINISSENT la marque)

#### 1. "Compatibilite" remplace "Match" — REGLE STRICTE

| Generique dating (interdit) | Compaatible (obligatoire) |
|-----------------------------|---------------------------|
| Match, matchs | **Compatibilite, compatibilites** |
| Tes matchs t'attendent | **Tes compatibilites arrivent** |
| 10 matchs par mois | **Jusqu'a 10 compatibilites par mois** |
| Trouver un match | **Trouver une compatibilite** |
| Liste de matchs | **Liste de compatibilites** |

**Pourquoi** : "Compatibilite" est le mot signature de la marque. Il porte la promesse de valeur (matching profond Big Five, pas swipe). "Match" est le vocabulaire generique des dating apps standard. En privilegiant "compatibilite", on differencie la marque a chaque ligne de copy.

**Tolerance code** : les variables (`match`, table `matches`, schemas, types `MatchData`) peuvent rester en anglais. La regle s'applique uniquement au copy visible.

**Synonymes acceptables selon contexte** : "rencontre(s)", "personne(s) compatible(s)", "connexion(s)".

#### 2. "Decouverte" / "Experience" remplacent "Free" / "Premium"

| Code (interne) | UI visible user |
|----------------|-----------------|
| `tier='free'` | **Decouverte** |
| `tier='premium'` ou `'paid'` | **Experience** |
| Plan gratuit | **Plan Decouverte** |
| Plan payant / Premium | **Plan Experience** |

Pas de prefixe "Plan" obligatoire dans les badges. Variables code intactes pour ne pas refondre les types.

#### 3. "Connexion" remplace "Demande" (systeme de connexion explicite)

| Generique (interdit) | Compaatible (obligatoire) |
|----------------------|---------------------------|
| Demande de match | **Connexion** |
| Envoyer une demande | **Initier une connexion** |
| Demande recue | **Connexion entrante** / "Connexion recue" |
| Demande envoyee | **Connexion envoyee** |
| Demandes en attente | **Connexions en attente** |

#### 4. "Debloquer" (mecanique) vs "Decouvrir" (engageant)

Distinction fine mais importante :

- **Debloquer** : action mecanique d'unlock d'une fiche verrouillee (potentiellement paywall). Utilise sur les cartes locked du reveal screen.
- **Decouvrir** : action engageante pour explorer un profil deja debloque (notamment via auto-unlock). Utilise sur match/[id] (CTA pending received) et connection-arriving.

#### 5. "Annonce des compatibilites" remplace "Revelation"

Toutes les occurrences de "Revelation", "Reveal", "Reveler" sont remplacees par **"Annonce des compatibilites"** dans le copy in-app. Le moment central du produit (le 1er et le 15) s'appelle l'**annonce**, pas la revelation (le mot reveal reste OK en code/routes).

#### 6. "Methode" / "Approche" / "Systeme de matching" remplacent "Algorithme"

Le mot **"algorithme" est interdit** dans tout copy visible. Toujours utiliser :

- "Notre methode"
- "Notre approche"
- "Notre systeme de matching"
- "Notre maniere de calculer la compatibilite"

#### 7. "App" / "Application" remplacent "Site"

Transition site → app effectuee. Le produit principal est mobile. Dire :

- ❌ "Sur le site" → ✅ "Dans l'app" / "Sur l'application"
- ❌ "Visite le site" → ✅ "Telecharge l'app"
- Exception : on peut parler du "site" pour designer specifiquement compaatible.com (funnel couple ou acquisition). Mais le PRODUIT, c'est l'app.

#### 8. "L'autre" / "personne" / "a deux" remplacent "tu/toi" dans les citations carte

Les citations affichees sur cartes profil (personality-punchlines.ts) ne doivent JAMAIS s'adresser au lecteur (pas de tu/toi/te/t'/ton/ta/tes). Voix "je", references abstraites/poetiques.

- ❌ "Tu n'auras pas a me convaincre"
- ✅ "Je n'ai pas besoin qu'on me convainque"
- ✅ "L'autre saura, ou ne saura pas"

**Exception** : icebreakers de chat (1:1) gardent l'adresse directe.

### Mots/concepts INTERDITS dans tout copy visible

| Mot/Concept | Raison | Remplacement |
|-------------|--------|--------------|
| **Tiret cadratin** (`—`, `–`) | Marqueur IA. Loys veut absolument l'eviter | `:` ou `.` ou reformuler avec virgule |
| **Algorithme** | Trop technique, froid, generique tech | "Methode", "approche", "systeme de matching" |
| **Scientifiquement prouve** (pour Compaatible) | Pretentieux + non verifiable juridiquement | "Base sur le Big Five (OCEAN)", "60 ans de recherche en psychologie" |
| **Science / scientifique** (in-app, post-onboarding) | Brise la magie de l'experience post-inscription | Formulation emotionnelle ou neutre |
| **Le site** | Le produit est l'app mobile | "L'app", "l'application" |
| **Lien en bio** (ads payantes) | Reserve au contenu organique | CTA App Store / Play Store explicite |
| **Unlock / unlocks** | Anglicisme tech opaque pour 35+ | "Debloquer", "compatibilites a debloquer" |
| **Match / matchs** (copy user) | Vocabulaire generique dating apps | "Compatibilite(s)" |
| **DM / direct message** | Anglicisme | "Message", "discussion" |
| **Swipe / swiper** | Vocabulaire des concurrents | A bannir, sauf critique frontale ("on ne swipe pas") |
| **Ghosting** | Anglicisme tech | "Silence", "absence de reponse" |
| **Feed** | Anglicisme | "Fil", "page" |
| **Feature** | Anglicisme | "Fonctionnalite", "option" |
| **Pseudo-science** | Non valide | A bannir |
| **5 astuces pour draguer** | Generique dating | Approche profondeur, pas tips |
| **Critique directe concurrents** | Rester factuel | Comparaison neutre, faits |
| **Jargon psy sans explication** | Inaccessible | Expliquer ou simplifier |
| **"C'est rare" pour un succes user** | Brand killer (suggere que Compaatible ne marche pas) | "C'est exactement ce qu'on cherche a provoquer" |
| **"Premier(s)" pour un user** (early adopter) | Lecture inverse : "donc il n'y a personne sur l'app" | Valoriser le PRODUIT en cours, pas l'user isole |

### Regles de ton (patterns d'ecriture)

#### Inversion sujet-verbe (ton premium, pas oral)

- ❌ "Comment tu t'appelles ?" (oral)
- ✅ "Comment t'appelles-tu ?" (premium)
- ❌ "C'est quoi ton rapport a l'argent ?" (oral)
- ✅ "Quel est ton rapport a l'argent ?" (premium)

#### Questions completes (pas de verbe en suspens)

- ❌ "Tes soirees ressemblent a ?"
- ✅ "A quoi ressemblent tes soirees ?"

#### Personnalisation par le prenom + verbes emotionnels

Quand on connait le prenom (`userName` disponible), l'utiliser dans les titres importants avec des verbes emotionnels intimes.

**Verbes emotionnels valides** : resonner en toi, te parler, te toucher, confier.

- ❌ "Selectionnes pour les ames lumineuses" (categorisation froide)
- ✅ "Marie, ces lectures peuvent resonner en toi" + "A partir de ce que tu viens de nous confier."

#### Lecture inverse obligatoire (test pessimiste)

Avant de valider un copy valorisant l'user ou l'etat du produit, **tester la lecture inverse** que ferait un prospect mefiant.

- ❌ "Tu fais partie des premiers profils analyses" → lecture inverse : "donc il n'y a personne sur l'app, je vais matcher avec personne"
- ✅ Valoriser le PRODUIT en cours de finalisation ("on rassemble les profils compatibles", "on finalise l'app") plutot que l'user en position d'isole.

**Toute promesse doit etre verifiable**. Pas de "tes matchs t'attendent" si les matchs ne sont pas generes.

#### Funnel couple : registre du "vous"

Sur les pages couple (invitation, resultats, rapport), le copywriting est centre sur le COUPLE, pas l'individu.

- ❌ "Quel type es-tu ?"
- ✅ "Etes-vous compatibles en amour ?"
- ❌ "Decouvre ta personnalite"
- ✅ "Decouvrez comment vous vous aimez"

Utiliser "vous/votre" pour parler du couple, "tu/ton" uniquement pour s'adresser DIRECTEMENT au partenaire invite.

#### Avant inscription vs apres inscription (transition de vocabulaire)

| Etape | Vocabulaire OK | Vocabulaire interdit |
|-------|----------------|----------------------|
| **Avant inscription** (landing, ads, emails de prospection) | "Base sur le Big Five (OCEAN)", "60 ans de recherche", "approche scientifique", "science de la personnalite" | "Scientifiquement prouve" (juridique), "algorithme" |
| **Apres inscription** (app, post-onboarding, in-app) | "Methode", "approche", "ce qu'on a mesure", formulations emotionnelles | "Science", "scientifique", "scientifiquement", "demarche scientifique" |

Une fois que l'user est "aware" du modele, le mentionner sans cesse devient pretentieux ou redondant. Ca brise la magie.

#### Citations carte profil (voix "je", abstraite/poetique)

Les `personality-punchlines.ts` (mobile + frontend, **synchroniser les deux**) decrivent comment la personne aime, pas ce qu'elle promet a un futur match. Voix "je", references a "l'autre", "personne", "a deux", "quand le lien est vrai".

### Pari anti-retention (la signature morale de Compaatible)

C'est LE pari produit central. Quand un user vit un succes (rencontre, date prevu, conversation qui continue) :

1. **Reconnaitre l'effort** : "Tu as fait partie de ceux qui ont su se donner les moyens de parvenir a leurs fins."
2. **Projeter vers le bonheur** : "Maintenant, tout le bonheur que tu merites t'attend."
3. **Porte ouverte sans pression** : "Et si un jour tu as besoin, nous serons toujours la."
4. **Hierarchie inversee des CTAs** : GROS bouton = "Refermer la page Compaatible" (anti-retention). Petit lien = "Rejoindre quand meme la prochaine session".

**Implementation** : `apps/mobile/app/session-closing/index.tsx::brandClosing(gender)`, partagee par les 3 tons positifs (met / date-planned / still-talking).

**Regle d'or anti-rare** : le succes user = la NORME que Compaatible cherche, pas une exception. Jamais "c'est rare", "tu fais partie des chanceux", "peu y arrivent". Toujours "c'est exactement ce qu'on cherche a provoquer", "c'est precisement pour ca qu'on existe".

### Patterns de copy valides (references)

#### Hero / Landing
- **Badge** : "Base sur la science de la personnalite" (avant inscription = OK)
- **Headline** : "Ton ame soeur existe. On va la trouver."
- **Subtitle** : "Fini les dates decevants et la solitude prolongee. Nous analysons ta personnalite en profondeur pour te presenter la personne la plus compatible avec toi."
- **CTA** : "Participe a l'experience" / "Telecharge l'app"
- **Trust badges** : "Donnees 100% confidentielles" / "Jusqu'a 10 compatibilites par mois" / "Sans abonnement"

#### Section "Comment ca marche" (3 etapes)
1. **"Fais le test"** : "Tu passes le test de personnalite approfondi. 15 minutes pour reveler ta personnalite profonde et ce que tu recherches vraiment."
2. **"On analyse"** : "Ton profil est compare aux autres participants sur 30 dimensions de personnalite."
3. **"Le 1er ou le 15"** : "Tu decouvres tes compatibilites. 2 fois par mois, tu recois des profils ultra-compatibles. Choisis celui qui te parle le plus et lance la conversation."

#### Story Section (anti-swipe)
- "La majorite des rencontres en ligne ne durent pas. Pourquoi ? Parce que ces plateformes matchent sur l'apparence, pas sur la personnalite."
- "Ici, on ne swipe pas. On se comprend."

#### Citations scientifiques utilisables (avant inscription)
- Dr. John Gottman : "La compatibilite psychologique est le meilleur predicteur de la satisfaction et de la longevite dans une relation."
- Helen Fisher : "L'amour romantique est une pulsion, aussi fondamentale que la faim ou la soif."
- Donnellan, Conger & Bryant (2004), Journal of Research in Personality.

#### Blog SEO — CTA fin d'article
"Trouve l'amour, une bonne fois pour toutes." + bouton "Fais le test gratuit".

### Ce que le CTA vend (toujours)

- ✅ Le CTA vend **la RENCONTRE / l'AMOUR**, pas le test.
- ✅ Le test est un MOYEN, pas la fin.
- ✅ Le CTA met en avant la PERSONNALITE > l'apparence physique.
- ❌ Ne JAMAIS vendre "passe un test marrant" comme produit final.

Le quiz est mentionne comme MECANISME ("tu passes un test"), jamais comme le produit lui-meme.

### Personas cibles (synthese)

**Demographie transversale** : France entiere (priorite grandes villes), 25-45 ans, introspectif, ouvert a la science, sceptique de la superficialite, francais educque.

| Persona court | Age | Douleur cle |
|---------------|-----|-------------|
| Le/La Fatigue(e) des apps | 25-35 | Swipe sans fin, dates decevants |
| Le/La Discret(e) professionnel | 28-40 | Peur d'etre vu(e) par un collegue/patient |
| Le/La Cerebral(e) / Rationnel(le) | 25-45 | Veut des donnees, pas du bullshit marketing |
| Le/La Serieux(se) | 28-40 | Fatigue(e) des plans d'un soir |
| Le/La Lucide Resigne(e) | 28-38 | A compris que la compatibilite compte, sans outil |
| Le Sceptique Connecte | 23-32 | Filtre anti-pub aiguise, blase |
| Le/La Curieux(se) de Soi | 20-30 | Quete de connaissance de soi (MBTI fan) |
| Le Guerrier (lasse en colere) | 26-35 | Marre des ghosteurs / swipeurs casuals |
| L'Introverti(e) Profondement Seul(e) | 25-35 | Pas d'opportunites, rejette les apps |
| L'Idealiste Reveur(se) | 25-40 | Cherche la profondeur, rejette la vulgarite |
| Le/La Fraichement Separe(e) | 25-40 | Sort d'une relation longue, veut comprendre |
| Le Parent Solo | 28-42 | Zero temps, veut qualite > quantite |

> Les 11 avatars detailles (douleurs, peurs, direction creative, hooks) sont dans `Compaatible-skills-main/avatars-personas.md`. **Toujours consulter avant de produire du contenu pour un avatar precis.**

### Canaux marketing actifs

#### Organique
| Canal | Cible | Ton | Objectif |
|-------|-------|-----|----------|
| TikTok (Madame Cupidon) | Femmes 22-35 | Complice, drole, girl-talk | Awareness + trafic app |
| Twitter / X | 22-40, introspectifs | Punchlines, observations | Autorite de marque |
| Reddit | 25-40, dating/psycho/FR | Authentique, valeur d'abord | Awareness + credibilite |
| Instagram @compaatible.app | Cross-target | Visuel premium | Brand + bonus story |

#### Email
- **Transactionnel + marketing** : Resend (domaine `send.compaatible.com`). Brevo retire en mai 2026.
- Email contact unifie : `contact@compaatible.fr`.
- Tout envoi marketing DOIT passer par `sendMarketingEmail()` (RGPD opt-in).

#### Ads payantes
- Meta Ads (Facebook + Instagram).
- Scripts produits par le skill **Ads Scriptwriter** (`Compaatible-skills-main/.claude/skills/ads-scriptwriter.md`).
- Angles tires de **`angles-marketing.md`**.
- CTA : App Store / Play Store. JAMAIS "lien en bio".

### Sources de verite marketing (ordre de lecture)

| Fichier | Role | Quand le consulter |
|---------|------|--------------------|
| `Compaatible-skills-main/context.md` | Identite produit, ton, regles copywriting, pricing | **Avant toute redaction de texte** |
| `Compaatible-skills-main/ads-performance.md` | Regles validees par donnees des campagnes reelles | **OBLIGATOIRE : prime sur la theorie** |
| `Compaatible-skills-main/angles-marketing.md` | Banque d'angles publicitaires actifs | Pour choisir l'angle d'un contenu |
| `Compaatible-skills-main/avatars-personas.md` | 11 avatars detailles | Pour cibler un persona precis |
| `Compaatible-skills-main/organique-script.md` | Scripts viraux de reference (mecanismes) | Pour s'inspirer |
| `Compaatible-skills-main/.claude/skills/` | Sub-skills : ads-scriptwriter, email-copywriter, site-copywriter, marketing-angles | Pour PRODUIRE du contenu |
| `Compaatible-skills-main/campagnes/` | Archives campagnes (donnees, scripts, analyses) | Reference historique |

**Workflow standard** : Marketing Angles cree dans `angles-marketing.md` → Ads Scriptwriter / Email Copywriter / Site Copywriter exploitent les angles.

### Glossaire marketing essentiel

| Terme | Definition |
|-------|-----------|
| **OCEAN** | Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism (5 domaines Big Five) |
| **Big Five** | Modele de personnalite en 5 facteurs, 60+ ans de recherche |
| **Facette** | Sous-dimension d'un domaine OCEAN (6 facettes par domaine = 30 total) |
| **Type / Profil** | L'un des 16 profils Compaatible (ex: "Papillon Empathique") |
| **Famille** | L'un des 4 regroupements (Architectes, Ames, Gardiens, Flammes) |
| **Session** | Periode de matching entre chaque annonce (2 sessions par mois) |
| **Le 1er et le 15** | Jours d'annonce des compatibilites chaque mois |
| **Annonce des compatibilites** | Le moment central produit (jamais "Revelation") |
| **Decouverte / Experience** | Plans gratuit / payant (jamais "Free / Premium" en UI) |
| **Connexion** | Demande de connexion bilaterale mutuelle (remplace "match request") |
| **UGC** | User Generated Content (format pub qui ressemble a de l'organique) |
| **NESB** | New, Easy, Safe, Big (4 piliers du subtext publicitaire, Kyle Milligan) |
| **LF8** | Life-Force 8 (8 desirs biologiques innes, Cashvertising) |
| **Hawkins** | Echelle de conscience emotionnelle (calibrer le ton des scripts) |

---

## 📐 Conventions de code

### TypeScript
- **Toujours** typer explicitement les props et return types des fonctions
- Utiliser `zod` pour la validation des données côté serveur
- Préférer les `interface` aux `type` pour les objets

### Next.js App Router
- Les Server Components sont le défaut — utiliser `'use client'` uniquement si nécessaire (interactivité, hooks)
- Les appels Supabase se font **côté serveur** (Server Components ou Route Handlers) sauf cas particuliers
- Les Route Handlers sont dans `app/api/`

### Supabase
- Toujours utiliser le client serveur (`createServerComponentClient`) dans les Server Components
- Le client navigateur (`createClientComponentClient`) uniquement dans les Client Components
- **Ne jamais** utiliser la `service_role_key` côté client
- Les migrations SQL passent par le dashboard Supabase ou CLI, jamais exécutées manuellement en prod

### CSS / UI
- Tailwind CSS en priorité
- Composants réutilisables dans `components/`
- Identité visuelle : low-poly géométrique, éléments cristallins, ruby heart logo facetté
- Palette principale : teintes profondes, premium, pas de couleurs criardes

---

## 🐛 Erreurs connues & règles apprises

### DNS / Infrastructure
- ❌ Ne jamais modifier les nameservers OVH sans vérifier l'impact sur Zoho Mail (MX records)
- ❌ Ne pas ajouter de CNAME sur le domaine racine (@) — utiliser un A record vers les IPs Vercel
- ✅ Le sous-domaine `send.compaatible.com` est dédié à Resend/SES — ne pas y toucher

### Supabase
- ❌ Ne jamais faire de `SELECT *` en production — toujours sélectionner les colonnes nécessaires
- ❌ Ne pas oublier les politiques RLS (Row Level Security) sur chaque nouvelle table
- ✅ Tester les policies RLS avec le compte anonyme avant de déployer

### Email
- ❌ Ne pas envoyer depuis `@compaatible.com` directement — utiliser `@send.compaatible.com`
- ✅ SPF, DKIM et DMARC sont configurés sur `send.compaatible.com`
- ❌ Ne JAMAIS envoyer un email marketing via `send()` direct → toujours `sendMarketingEmail(to, subject, html)` qui skip silencieusement si `users.marketing_opt_in_at IS NULL`. Sinon = traitement illegal RGPD (Article 7.4).
- ✅ Email contact unifie : `contact@compaatible.fr` (pas `.com` dans le legalNotice).

### RGPD (mai 2026)
- ❌ Ne JAMAIS rendre l'opt-in marketing obligatoire au signup (illegal, Article 7.4 + Planet49). Toujours **opt-in facultatif separe** du CGU.
- ❌ Ne JAMAIS skip le check age 18+ backend (cote client zod = contournable). Le check est dans `auth_controller.register/googleRegister` ET `users_controller.update`.
- ✅ Si on ajoute une nouvelle categorie de donnees collectees → DOIT apparaitre dans `processing.purposes` ET `data` de `GET /api/me/export`.
- ✅ Si on ajoute un sous-traitant → DOIT etre ajoute a `processing.recipients` de l'export RGPD.
- ✅ Si la methode de matching change (nouveaux inputs/outputs) → mettre a jour les 3 surfaces simultanement : pol. conf. section 9, FAQ mobile, export JSON `processing.automatedDecisionMaking`.
- ❌ Ne JAMAIS utiliser les donnees blacklist a d'autres fins que l'exclusion du matching (pas de profilage, pas d'export tiers).
- ✅ Delais de suppression : 30 jours (bases prod) + 6 mois (sauvegardes chiffrees) + 10 ans (transactions). Aligne sur 4 surfaces : pol. conf., FAQ x2, export.

### Connexions explicites (mobile)
- ❌ Ne JAMAIS reactiver le chat ouvert par defaut. Toute conversation passe par `connection_status = 'accepted'`. Le `messages_controller` refuse `POST messages` si pas accepted (403 `connection_not_accepted`).
- ❌ Ne pas confondre `refused` et `expired` dans le copy. Refused = ton empathique ("droit de B"). Expired = message anti-ghosting.
- ✅ Vocabulaire : "Connexion" pas "Demande" dans le copy in-app. "Debloquer" (mecanique) vs "Decouvrir" (engageant).
- ✅ Auto-unlock cote B : si A initie sur un match dont B n'a pas encore unlocked, backend auto-unlock cote B SANS decrementer son quota. Le mobile joue `/connection-arriving/[id]` (animation) avant `/connection-request/[id]`.
- ✅ Compensation refus en serie : 3+ connexions refused/expired sans aucune accepted (rolling 30j, frein 90j entre 2 compensations) → code promo personnel 100% sur Experience, 60 jours.
- ✅ Le countdown 48h dans `ReceivedRequestRow` est live (re-render via `useTick(60_000)`). Format "Tu as Xh MM pour y repondre".

### Bot Compaatible (feedback)
- ❌ Le bot ne repond JAMAIS aux questions ouvertes. Toujours rediriger vers `/support` (entonnoir FAQ).
- ❌ Ne pas ajouter de quick reply free-form. Toujours chips de presets structurees (`free_feedback` state).
- ✅ Les 4 states (`free_feedback`, `bonus_pending`, `bonus_under_review`, `feedback_done`) sont calcules cote backend dans `feedback_controller.messages()`. Le mobile ne fait que rendre.
- ✅ Le bot dans les chats matchs (`type='system'` dans table `messages`) est distinct du bot feedback. Narrateur silencieux : intro + icebreaker + goodbye + last_word.

### Support FAQ (entonnoir)
- ❌ Ne pas mixer les sources de tickets cote admin. `SupportPanel` = source='app' uniquement. `SavPanel` = email/form/manual.
- ✅ 7 categories alignees entre mobile (`support.tsx::FAQ`), backend (`support_controller.ts::vine.enum`), admin (`SupportPanel.tsx::CATEGORY_LABELS`). Toute modif d'une categorie doit toucher les 3.
- ✅ Le formulaire pre-remplit categorie + sujet (question consultee) automatiquement.

### Notifications push (6 cron GitHub Actions)
- ❌ Ne pas dupliquer ces 6 cron dans Railway. Source de verite = `.github/workflows/push-notifications-cron.yml`.
- ❌ Ne JAMAIS mettre 2 infos dans 1 push. Toujours splitter en 2 pushes distincts (regle Loys).
- ✅ Cron horaire `expiration-connexions` est critique : passe les connexions pending > 48h en `expired` + push aux initiateurs. Ne pas le casser sans alternative.
- ✅ Push opaque ("Un message t'attend", "Nouveau message") utilise pour : relance bot bonus, compensation refus continu. Garder l'effet de surprise.

### Paiement (IAP Apple/Google via RevenueCat, mobile)
- **App mobile** : **pas de Stripe**. L'app est distribuée via App Store + Play Store → obligation d'utiliser les IAP natifs (Apple In-App Purchase / Google Play Billing). Sinon rejet store.
- RevenueCat est l'orchestrateur côté client (`apps/mobile/lib/purchases.ts`). Entitlement actif : `premium`.
- Modèle commercial : **abonnement 9,99€/session** (voir `project_pricing_subscription.md` en mémoire). Apple/Google ne supportent pas nativement un cycle "tous les 15 jours" → choix technique du cycle IAP encore à trancher (subscription mensuelle pilotée backend / consumables / weekly).
- Les SKUs legacy `premium_weekly` / `premium_monthly` / `photo_enhance_199` sont à refondre. Ne pas les considérer comme la source de vérité du pricing.
- ❌ Ne JAMAIS afficher "Paiement unique" ou "Annuel -40%" dans le paywall mobile : c'est legacy et incohérent avec l'abonnement par session
- ❌ Ne JAMAIS communiquer sur "19,99€/mois" même si techniquement c'est 2 sessions × 9,99€. Wording UI : "9,99€ par session"
- ✅ Toujours expliquer le crédit reporté quand on parle du prix (rassure l'utilisateur sur le no-loss en cas de session loupée)

### Paiement site web (rapport couple 4,99€)
- Stripe a historiquement été utilisé pour le rapport couple sur le site web
- ⚠️ Statut à confirmer après le pivot mobile vers IAP (mai 2026). Ne pas modifier le paywall site web sans validation explicite de Loys.
- Si Stripe reste actif côté site : pas de stockage de carte en base, toujours passer par les webhooks Stripe pour confirmer les paiements.

### Redaction / Copywriting
- Voir la section **📣 Marketing & Copywriting** ci-dessus pour toutes les regles de redaction et le dossier de reference `Compaatible-skills-main/`.
- ❌ Ne JAMAIS ecrire du texte visible sans accents francais (é, è, ê, à, ù, etc.). Toujours relire avant de valider.
- ❌ Ne pas repeter "Ton profil est pret" sur plusieurs ecrans consecutifs. L'utilisateur le sait deja.
- ✅ Le CTA couple vend la DECOUVERTE A DEUX, pas le test. Notion de partage et de "ensemble".
- ✅ Copywriting couple : toujours s'adresser au "vous" (le couple), ton chaleureux et emotionnel.

### UX / Funnel couple
- ❌ Ne pas creer de pages intermediaires qui forcent un clic supplementaire sans valeur ajoutee. Un clic = une intention.
- ❌ Ne pas proposer "Pas maintenant" ou "Plus tard" sur les etapes critiques du funnel couple (invitation partenaire).
- ✅ Le partenaire invite clique le lien → arrive directement sur signup/test (pas de landing intermediaire).
- ✅ La page d'envoi d'invitation (ResultatsView couple) montre ce qui se debloque ensemble (cadenas + liste).
- ✅ Les visuels couple (cartes, cercle compatibilite) ne doivent pas dupliquer l'avatar deja visible dans le hero.

### Design / Visuels
- ❌ Ne pas utiliser de fond colore par categorie (vert, violet, etc.) sur les CTA cards. Utiliser le burgundy #8B2D4A ou blanc.
- ❌ Ne pas superposer des elements dans les cartes reduites (zoom/scale). Verifier visuellement.
- ✅ Les cadenas (stroke, pas fill) sont le bon style pour les elements verrouilles.
- ✅ Le glassmorphism (fond blanc semi-transparent + backdrop-blur) est le style du cadenas sur le teaser.
- ✅ Les 3 coeurs Compaatible (1 central anime + 2 lateraux en fond a 15% opacite) = visuel couple standard.

### Vue 3 / Frontend
- Composition API avec `<script setup lang="ts">`
- Les appels API utilisent le wrapper `apiFetch` de `lib/api.ts`
- Ne pas utiliser `next/router` (c'est Vue, pas Next.js) — utiliser `vue-router`

### App mobile (Expo / React Native)
- Framework : Expo Router (file-based routing)
- State : Zustand (auth store, onboarding store)
- Style : NativeWind (Tailwind pour React Native)
- Token : Expo SecureStore (pas AsyncStorage pour les tokens)
- `MOCK_ENABLED = true` dans `mockData.ts` : passer a `false` pour la prod
- Endpoints manquants dans le backend : `/api/auth/apple`, `/api/photo-ai/*`

### Archive des pages inutilisées
- ✅ Les pages/views qui ne sont plus utilisées en prod doivent être déplacées dans `apps/frontend/src/views/_archive/` et retirées du routeur (`router/index.ts`)
- ✅ Ne jamais supprimer une page : toujours archiver dans `_archive/` pour pouvoir la restaurer
- Pages archivées : `DevPlaygroundView.vue`, `PhotoUploadView.vue`, `AdminView.vue`

### Backend / Validators (AdonisJS Vine)
- ❌ Ne JAMAIS modifier un validator `vine.array` → `vine.record` (ou inverse) sans verifier les DEUX clients (web + mobile). Le frontend web envoie `answers` et `idealPartner` comme **Array** (legacy depuis l'origine) tandis que le mobile envoie `answers` comme **Record/Object**. Un changement unilateral casse silencieusement le store qui retourne 422 → `personality_type` reste null → l'user est renvoye sur `/test` apres verification email.
- ✅ Pour `test_results.store`, garder `answers: vine.any()` et `idealPartner: vine.any().optional()` jusqu'a ce que les deux clients soient unifies sur le meme format (Record cote DB).
- ✅ Avant de toucher a un validator, grep `apps/frontend/` ET `apps/mobile/` pour voir tous les call sites qui envoient ce champ.

### Vue / Vite (frontend)
- ❌ Ne jamais utiliser `export { foo } from './module'` pour réexporter une fonction qu'on utilise aussi dans le même fichier. Vite dev est permissif mais le build prod lève un `ReferenceError: foo is not defined`. Toujours faire `import { foo } from './module'` puis `export { foo }` séparément.
- ❌ Ne pas oublier d'ajouter les domaines backend dans le `connect-src` du CSP (`public/_headers`). Un CSP trop restrictif bloque silencieusement les requêtes `fetch` sans erreur CORS — le backend ne reçoit rien et le frontend affiche "Erreur de connexion". Domaine Railway à autoriser : `https://*.railway.app`.
- ❌ Ne jamais utiliser `navigator` ou d'autres globaux du navigateur directement dans le `<template>` Vue. Vue ne les expose pas dans le scope du template → provoque un `ReferenceError` silencieux qui crashe tout le rendu de la page (page blanche). Toujours créer une variable dans le `<script setup>` : `const canShare = typeof navigator !== 'undefined' && !!navigator.share`.
- ❌ Ne jamais utiliser `v-if` indépendants pour des conditions mutuellement exclusives. Utiliser `v-if / v-else-if / v-else` pour que Vue n'évalue qu'une seule branche. Les `v-if` indépendants sur le même bloc sont évalués tous à chaque render.
- ❌ Quand on utilise `sed` sur des fichiers Windows (CRLF `\r\n`), les expressions régulières avec `\n` ne matchent pas. Préférer l'outil Edit de Claude ou un script Node qui détecte le format de ligne (`content.includes('\r\n')`). Un `sed` mal calibré peut vider un fichier entier.
- ❌ Quand on supprime un wrapper `<div>` (ex: `cr-section-body`) dans un template, penser à supprimer aussi le `</div>` correspondant plus bas. Un `</div>` orphelin provoque "Element is missing end tag" au build.

### Funnel couple (site web)
- ❌ Ne pas montrer "Inviter mon/ma partenaire" au partenaire invité. La PersonalityReveal doit distinguer initiateur vs invité via `coupleReportReady`.
- ❌ Le polling `invitationStatus` doit avoir une durée max (30 min) et un ralentissement progressif (15s → 30s) pour ne pas surcharger le backend. Toujours nettoyer le timer dans `onUnmounted`.
- ❌ L'invitation couple expire en 48h (pas 7 jours). Quand elle expire, le status passe de `invitation_pending` à `none` côté API.
- ✅ Le zoom CSS est la meilleure approche pour scaler proportionnellement un layout carte + cercle + carte. Ne pas contraindre la largeur des cartes, laisser le zoom faire.
- ✅ La section "Votre parcours à deux" (roadmap) ne doit pas supposer que le couple est nouveau. Utiliser "Se (re)découvrir" au lieu de "Se découvrir".

### Architecture site : deux espaces, pas de page profil classique (avril 2026)
- ❌ Le site n'a PAS de dashboard matchs/sessions/countdown. Tout le matching se passe dans l'app mobile. Le site sert uniquement a l'acquisition (celibataires → app) et au rapport couple (couples → paiement rapport 4,99€, processeur à confirmer).
- ❌ Ne jamais afficher le TYPE de personnalite sur le site. Seule la CATEGORIE (famille) est montree sur le teaser. Le type se revele dans l'app mobile (celibataires) ou dans le rapport couple (couples).
- ❌ Ne jamais laisser un utilisateur sans test acceder a `/profil` ou `/teaser`. Toujours rediriger vers `/test`.
- ✅ Le `couple_invitation_token` est stocke dans `localStorage` (pas sessionStorage) pour survivre a la fermeture du navigateur. Pour le lancement a grande echelle, stocker le token d'invitation en base (table `users`) cote backend.
- ❌ Ne pas pointer un lien "Retour au profil" vers `/profil` dans des pages accessibles aux celibataires. `/profil` redirige les celibataires vers `/teaser`. Utiliser `/teaser` comme destination de retour universelle.
- ✅ `/teaser` = espace celibataire. 3 etapes integrees : calcul → categorie → carte floutee + CTA app. Pas de toggle statut (gere dans l'app mobile).
- ✅ `/profil` = espace couple uniquement. 3 etats : invitation (state=none), en attente (state=pending), rapports (state=reports). Affiche l'avatar du TYPE (pas la categorie). Deconnexion en haut.
- ✅ Le couple voit le reveal COMPLET (5 etapes) dans `/resultats/:id` puis est redirige vers `/profil` (invitation). Utiliser `navigateOnFinish=false` et `maxStep=-1` pour les couples dans ResultatsView.
- ✅ Le celibataire voit un reveal LIMITE (etapes 0 + 1 seulement, maxStep=1) integre directement dans TeaserAppView, pas via PersonalityReveal (qui crashe dans ce contexte).
- ✅ Le choix celibataire/couple se fait AVANT le test ("Quelle est ta situation en amour ?"). Les couples sautent partenaire ideal + photo. Le statut est sauvegarde dans sessionStorage et prerempli dans l'inscription.
- ✅ Le changement de statut ne se fait PAS sur le site (pas de toggle). Il se gere dans l'app mobile et se synchronise via la base.
- ✅ Les cartes de rapport couple utilisent une couleur burgundy uniforme (#8B2D4A) avec cercle de progression SVG. Pas de couleurs variables (vert/ambre/rouge).
- ❌ Ne JAMAIS charger le script Google GSI ou PostHog si la cle d'API n'est pas configuree. Ca ralentit la page pour rien en dev local.
- ❌ Quand on utilise `transform: scale()` pour reduire un composant, utiliser `transform-origin: top center` et un `margin-bottom` negatif pour compenser l'espace vide. Ne PAS utiliser `max-width` pour reduire (ca coupe au lieu de scaler).
- ✅ `/profil` = espace couple uniquement (invitation, rapports, toggle "Je suis celibataire", deconnexion). Redirige les celibataires vers `/teaser`.
- ✅ Le cooldown de changement de statut est asymetrique : couple → celibataire = instantane (rupture), celibataire → couple = 24h (anti-abus sessions).
- ✅ Le post-login routing se fait dans `ConnexionView.routeAfterLogin()` : celibataire → `/teaser`, couple → `/profil`. Si aucun test n'existe → `/test`. Les redirections pendantes (invitation couple) sont prioritaires via `compaatible_redirect_after_login`.
- ✅ Les fonds de categorie sont toujours pastels (bgColor ou color + '1a') avec texte de la couleur de categorie. Jamais de fond fonce + texte blanc sur les badges de categorie.

---

## 🧪 Tests & qualité

- Avant chaque PR : `npm run build` doit passer sans erreur
- Tester le funnel complet (test Big Five → résultats → inscription) à chaque modification majeure
- PostHog est la source de vérité pour valider que les events sont bien trackés

---

## 🤖 Instructions pour les agents parallèles

### Règles de base
- **Ne jamais toucher aux migrations Supabase** sans validation explicite de Loys
- **Ne jamais modifier `.env.local`** ni les variables d'env Vercel
- **Ne jamais pusher directement sur `main`** — toujours passer par une branche feature
- Chaque agent travaille sur des fichiers distincts pour éviter les conflits

### Decoupe recommandee pour le travail en parallele
```
Agent 1 (Site web)   → apps/frontend/ (Vue 3, landing page, SEO)
Agent 2 (App mobile) → apps/mobile/ (Expo, React Native)
Agent 3 (Backend)    → apps/backend/ (AdonisJS, API, services)
Agent 4 (Admin)      → apps/admin/ (React, panel admin)
Agent 5 (SEO/Blog)   → contenu articles, pages programmatiques
```

### Communication entre agents
- Chaque agent documente ses changements dans un fichier `AGENT_LOG_[nom].md` temporaire
- En cas de conflit potentiel sur un fichier, stopper et demander arbitrage

---

## 📊 Métriques clés à ne pas casser

| Métrique | Seuil critique |
|----------|----------------|
| Conversion test_started → test_completed | > 70% |
| Conversion results_viewed → signup_completed | > 30% |
| Score Lighthouse Performance | > 85 |
| Build time Vercel | < 3 min |

---

## 🔍 Stratégie SEO programmatique

### Volume total de pages par cluster

| Cluster | Pages | Calcul |
|---------|-------|--------|
| C1 — Tests & compatibilité | **138 pages** | 2 pages fixes + 136 pages profil×profil (C(16,2)=120 combinaisons uniques + 16 same-profile) |
| C2 — Rencontre sérieuse | **3 pages** | 3 pages fixes |
| C3 — Blog (existant) | **∞ articles** | Généré automatiquement via n8n + Supabase — déjà en place |
| C4 — Villes | **200 pages** | 2 templates × 100 villes françaises |
| C5 — Contenu viral | **3 pages** | 3 pages fixes |
| **TOTAL** | **~344 pages** | Hors articles de blog |

> **Calcul profil×profil** : 16 profils → C(16,2) = 120 combinaisons A≠B + 16 combinaisons A=A (ex: "deux Papillons ensemble") = **136 pages uniques**. Les 120 URLs inverses (`B-A`) font une 301 vers `A-B`.

### Priorité d'implémentation
1. **Phase 1** — Pages profil×profil (136 combinaisons uniques) ✅ **FAIT (mars 2026)**
2. **Phase 2** — Alternatives apps ✅ **FAIT (mars 2026)** — pages statiques rencontre sérieuse restantes à faire
3. **Phase 3** — Blog existant — déjà actif, optimiser le maillage interne vers C1/C2
4. **Phase 4** — Pages villes — volume long-tail cumulatif
5. **Phase 5** — Contenu viral — notoriété + partages

### 🟢 Clusters implémentés

| Cluster | Statut | Fichiers clés | Date |
|---------|--------|---------------|------|
| **C1 — Pages profil×profil** | ✅ Déployé | `CompatibiliteProfilsView.vue`, route `/compatibilite/:profil1/:profil2`, `sitemap-compatibilite.xml` (136 URLs) | Mars 2026 |
| **C2 — Alternatives apps** | ✅ Déployé | `AlternativeAppView.vue`, `alternative-apps.ts`, route `/alternative/:app` (6 apps : Yoyomatch, Tinder, Bumble, Hinge, Meetic, Adopte) | Mars 2026 |

### Notes C2 — Alternatives apps
- Le vrai différenciateur vs Yoyomatch : **quiz maison non validé** (questions changeantes) vs **Big Five OCEAN** (60 ans de recherche)
- Points communs honnêtes avec Yoyomatch à ne pas nier : rythme mensuel, pas de messagerie intégrée (contact via Instagram ou numéro direct), pool limité grandes villes
- Pages statiques restantes à créer : `/rencontre-serieuse`, `/meilleure-app-rencontre-serieuse`

### Convention animations (établie mars 2026)
- **Scroll reveal** : `IntersectionObserver` + classes `.reveal` / `.is-visible` (opacity + translateY)
- **Hover cards** : CSS scoped avec `cubic-bezier(0.34, 1.4, 0.64, 1)` (spring) — NE PAS utiliser les classes Tailwind `hover:translate-*` sur des éléments qui ont déjà une transition reveal (conflit de transform)
- **Hover boutons** : spring + `will-change: transform` + flèche `translateX` via `.btn-arrow`
- **Easing référence** : reveal = `cubic-bezier(0.4, 0, 0.2, 1)` / hover lift = `(0.34, 1.4, 0.64, 1)` / icon pop = `(0.34, 1.6, 0.64, 1)`

---

### Cluster 1 : Tests de personnalité et compatibilité (cœur USP)
**Objectif** : Convertir le trafic organique en utilisateurs via l'USP Big Five.

| Route | Intention SEO | Notes |
|-------|--------------|-------|
| `/test-compatibilite-amoureuse` | "test compatibilité couple", "test personnalité relation", "quel type de personnalité suis-je amoureux" | Page principale — absorbe `/test-personnalite-amour` (fusionnés pour éviter cannibalisation). Présente les 30 dimensions, 16 profils, et CTA test. |
| `/compatibilite-couple` | "compatibilité amoureuse", "score compatibilité couple" | Guide + témoignages anonymisés. Section dédiée aux 16 profils (remplace `/types-de-personnalite-amour` supprimé). |
| `/compatibilite/{profil1}-{profil2}` | "compatibilité [Profil A] et [Profil B]" | **136 pages programmatiques** (120 combinaisons uniques A≠B + 16 same-profile — voir règle anti-doublon ci-dessous) |

> ⚠️ **Règle anti-doublon pour les pages profil×profil** : Ne générer que les combinaisons où `profil1 ≤ profil2` (ordre alphabétique). `/compatibilite/papillon-stratege` existe, `/compatibilite/stratege-papillon` redirige via 301 vers la première. Les 16 pages same-profile (ex: `/compatibilite/papillon-papillon`) sont valides et pertinentes SEO ("deux profils identiques en couple ?").

Contenu type pour `/compatibilite/{profil1}-{profil2}` : description des deux profils, forces/faiblesses en couple, dynamique communication/humour/valeurs, CTA test, FAQ "Comment fonctionne le test ?".

---

### Cluster 2 : Rencontre sérieuse / alternatives apps
**Objectif** : Capter les recherches de rencontre sérieuse et positionner Compaatible comme alternative scientifique.

| Route | Intention SEO | Notes |
|-------|--------------|-------|
| `/rencontre-serieuse` | "rencontre sérieuse", "site rencontre sérieux", "application rencontre sérieuse", "trouver l'amour" | Page principale — absorbe `/site-rencontre-serieux` (fusionnés). Met en avant la différence Big Five + CTA test. |
| `/meilleure-app-rencontre-serieuse` | "meilleure app rencontre" | Tableau comparatif objectif vs Tinder/Bumble/Hinge. Angle : "voici les options, voici pourquoi Compaatible est différent". |
| `/alternative-tinder` | "alternative tinder", "apps rencontre sans swipe" | Angle émotionnel "j'en ai marre de swiper". Expliquer le no-swipe et le matching profond. |

> ⚠️ `/rencontre-serieuse` et `/site-rencontre-serieux` étaient trop proches — **une seule page** avec les deux intentions via le contenu et les balises meta.

---

### Cluster 3 : Blog (déjà existant — pipeline n8n + Supabase)
**Objectif** : Trafic organique éducatif + autorité de domaine + backlinks naturels.

> ✅ **Ce cluster correspond au blog déjà en place**, généré automatiquement via n8n + Supabase (`table articles`). Les articles couvrent la psychologie du couple, la compatibilité, le Big Five, etc.

**Action à faire** : optimiser le maillage interne du blog vers les clusters 1 et 2 :
- Chaque article doit pointer vers `/test-compatibilite-amoureuse` (CTA)
- Les articles mentionnant des profils doivent pointer vers les pages `/compatibilite/{profil1}-{profil2}` correspondantes
- Les articles sur la rencontre doivent pointer vers `/rencontre-serieuse` ou `/alternative-tinder`

> ⚠️ `/types-de-personnalite-amour` supprimé — son contenu est intégré dans `/compatibilite-couple` et `/test-compatibilite-amoureuse` pour éviter la cannibalisation.

---

### Cluster 4 : Long-tail par ville (cumulatif)
**Objectif** : Trafic localisé longue traîne — faible volume par page mais cumul significatif.

| Route template | Intention SEO |
|---------------|--------------|
| `/ville/{nom-ville}/rencontre-serieuse` | "rencontre sérieuse Paris", "site rencontre Lyon" |
| `/ville/{nom-ville}/test-compatibilite` | "test compatibilité Toulouse", "test personnalité amour Bordeaux" |

Contenu type : intro spécifique à la ville, conseils locaux, CTA test. Généré statiquement depuis une liste de villes françaises.

---

### Cluster 5 : Contenu viral et partageable
**Objectif** : Backlinks naturels + trafic social + notoriété.

| Route | Intention SEO | Notes |
|-------|--------------|-------|
| `/quiz/quel-type-de-personnalite-suis-je` | "quel type de personnalité amoureux" | **Vraiment interactif** (résultats immédiats en JS) — différencié de `/test-compatibilite-amoureuse` par le format, pas l'intention |
| `/guides/comment-fonctionne-la-compatibilite` | "compatibilité couple", "matching scientifique" | Guide éducatif long-form + conversion |
| `/blog/pourquoi-le-matching-fonctionne` | "compatibilité psychologique amour" | Storytelling + CTA |

> ⚠️ `/quiz/...` et `/test-compatibilite-amoureuse` ciblent une audience similaire — les différencier impérativement par le **format** (quiz interactif avec résultats immédiats côté client vs landing test complet). Sans cette distinction, risque de cannibalisation.

---

### Conventions SEO programmatique
- Pages profil×profil générées via `generateStaticParams` (Next.js SSG)
- Combinaisons miroir (`B-A`) → redirect 301 vers (`A-B`) — ne jamais générer les deux
- Chaque page programmatique a un `title`, `description` et `canonical` unique via `generateMetadata`
- Pages villes générées statiquement depuis un fichier `data/villes-fr.ts`
- Maillage interne obligatoire : profil → compatibilités → test → inscription
- Toutes les pages SEO incluent un CTA vers le test gratuit

---

## 🔄 Process de mise à jour de ce fichier

**Après chaque session de code :**
1. Si une erreur a été commise → ajouter dans "Erreurs connues & règles apprises"
2. Si une nouvelle convention a été établie → ajouter dans "Conventions de code"
3. Si l'architecture change → mettre à jour la section correspondante

**Pendant une code review :**
- Taguer `@claude` sur les PRs pour que Claude suggère des ajouts à ce fichier

---

*Derniere mise a jour : Mai 2026 — v2.3 (refonte profonde de la section Marketing & Copywriting : ADN marque, vocabulaire signature "compatibilite > match", regles de ton, pari anti-retention, distribution tonale 40/40/20, mots interdits, 11 personas, sources Compaatible-skills-main. En plus de v2.2 (coeur conceptuel Big Five + algorithme) et v2.1 (parcours utilisateur))*
