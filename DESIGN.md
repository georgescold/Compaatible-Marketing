# DESIGN.md — Compaatible

> Source de verite design du projet. Consolide la palette, les typos, les couleurs des 4 familles, les conventions visuelles et les regles d'animation.
> Toute modification visuelle majeure doit etre repercutee ici.

---

## Philosophie design

**Compaatible est une marque premium, epuree, romantique.** Le design respecte trois principes :

1. **Premium** : pas d'elements amateurs (cercles numerotes, grilles surchargees, bordures rondes inutiles). Beaucoup de whitespace, layouts minimalistes.
2. **Romantique** : palette burgundy chaude, typographies serifs elegantes (Playfair, Cormorant), elements cristallins (ruby heart facette).
3. **Lucide et serieux** : pas de couleurs criardes, pas de stickers, pas d'emoji dans l'UI sauf hobbies. Le ton visuel doit refleter la profondeur du Big Five.

L'utilisateur doit comprendre l'intention d'un ecran en 3 secondes.

---

## Palette de marque

### Couleurs principales

| Role | Hex | Usage |
|------|-----|-------|
| **Burgundy** (primaire) | `#8B2D4A` | Couleur signature de la marque. CTA, accents, logo, etats actifs. |
| **Rose profond** | `#B5001F` | Variante secondaire pour gradients et hover. |
| **Plum** | `#7A0016` | Variante sombre pour fonds premium et paywall. |
| **Creme** | `#FBF9F7` | Fond principal des pages web. Doux, chaud, jamais blanc pur. |

### Couleurs neutres

| Role | Hex | Usage |
|------|-----|-------|
| Ink (texte principal) | `#1F1115` | Texte body. Jamais noir pur. |
| Muted (texte secondaire) | `#8B7D85` | Sous-titres, labels. |
| Hairline (bordures) | `#EFE6E9` | Bordures cartes, separateurs. |
| Glass (overlay) | `rgba(255,255,255,0.6)` | Glassmorphism + backdrop-blur. |

### Couleurs systeme

| Role | Hex | Usage |
|------|-----|-------|
| Success | `#5E8A72` | Vert sauge (jamais vert vif). Aligne sur la famille Ames. |
| Warning | `#B8783D` | Ambre (jamais orange criard). Aligne sur la famille Flammes. |
| Error | `#B5001F` | Reutilise le rose profond. Pas de rouge pompier. |

> Regle : ne jamais introduire une couleur en dehors de cette palette. Si un cas demande une nouvelle teinte, derivée par opacite (`+'1A'` pour 10% par exemple) plutot que par nouvelle valeur.

---

## Couleurs des 4 familles de personnalite

Adoucies en avril 2026 pour coherence avec le burgundy. **Toujours importer depuis** `apps/mobile/data/personality-types.ts` ou `apps/frontend/src/data/personality-types.ts`. Ne jamais hardcoder.

| Famille | Couleur | Background pastel | Symbolique |
|---------|---------|-------------------|------------|
| **Architectes du Coeur** | `#7B5EA7` (violet) | `#F5F0F9` | Vision, ambition, exigence |
| **Gardiens du Lien** | `#4A857E` (teal) | `#F0F6F5` | Loyaute, fiabilite, soin |
| **Ames Lumineuses** | `#5E8A72` (vert sauge) | `#F2F7F4` | Empathie, douceur, profondeur |
| **Flammes Libres** | `#B8783D` (ambre) | `#FAF4ED` | Liberte, audace, intensite |

### Regles d'usage des couleurs famille

- ✅ Fond pastel (`bgColor` ou `color + '1A'`) avec texte de la couleur famille pour les badges/pills.
- ✅ Bordures et ombres tres legeres (`color + '1F'` opacite 12%) pour des cards subtilement teintees par famille.
- ✅ Gradient diagonal famille pour cartes contextuelles : `[${color}1A → ${color}08 → #fff]`.
- ❌ **Jamais de fond fonce + texte blanc** sur les badges de categorie (rend l'UI agressive).
- ❌ **Jamais de couleur famille sur les CTA principaux**. Les CTA restent burgundy `#8B2D4A` ou blanc.
- ❌ Jamais de couleur famille en bloc plein (Ex: bouton vert sauge), uniquement en accent / fond pastel.

---

## Typographies

### Hierarchie

| Famille | Police | Usage |
|---------|--------|-------|
| **Display / titres** | **Playfair Display** (serif) | H1, H2, hero, noms de types de personnalite, headers ceremonieux |
| **Body / UI** | **Inter** (sans-serif) | Paragraphes, labels, boutons, navigation, formulaires |
| **Citations / italic** | **Cormorant Garamond** (serif, elegant) | Insights match, citations user (customTagline en italic), passages premium |
| **Eyebrows / kicker** | Inter uppercase 10-11px letter-spacing wide | Labels au-dessus des titres (ESPACE COMPAATIBLE, CONNEXION ENTRANTE, etc.) |

### Tailles de reference (mobile)

| Element | Police | Taille |
|---------|--------|--------|
| Hero title | Playfair | 28-32px |
| Section title (eyebrow + titre) | Playfair | 22-24px |
| Card title | Playfair | 17-19px |
| Body | Inter | 15-16px |
| Caption / sous-titre | Inter | 13-14px |
| Eyebrow | Inter uppercase | 10-11px (letter-spacing 1.5-2px) |
| Citation italic | Cormorant Garamond italic | 17-19px |

### Regles typographiques

- ✅ Inversion sujet-verbe sur les titres premium ("C'est ici que tout commence" plutot que "Tout commence ici").
- ✅ Jamais de verbe en suspens (sauf icebreakers casuals).
- ✅ Toujours les accents francais (e, e, e, a, u, etc.). Jamais d'oubli.
- ❌ Pas de tiret cadratin (`—`, `–`). Marqueur IA. Utiliser `:`, `.` ou reformuler.

---

## Identite graphique

### Logo

**Ruby Heart** : coeur facette low-poly burgundy. Le symbole de la marque.

- Sur les ecrans intimes (chat sys-left, chat opening, FeedbackBot avatar) : utilise comme avatar narratif "Compaatible".
- Sur le tab Home : remplace l'icone par defaut. Compose avec eyebrow "ESPACE COMPAATIBLE".
- Animation : pulsation tres douce (3-4s loop), opacity 0.22 a 0.4. Pas d'onde, pas de scale agressif.
- **3 coeurs visuel couple** : 1 central anime + 2 lateraux a 15% opacite en fond. Pattern recurrent sur les pages couple.

### Style visuel

- **Low-poly geometrique** : facettes triangulaires, formes anguleuses douces.
- **Elements cristallins** : transparences, gradients legers, jamais d'opacite plate.
- **Glassmorphism** : fond blanc semi-transparent (`rgba(255,255,255,0.6)`) + `backdrop-filter: blur(12-16px)`. Style des cadenas sur le teaser.
- **Cadenas (stroke, pas fill)** : pour tous les elements verrouilles. Trait fin, jamais rempli.

### Avatars vs Photos

- **Avatar** = SVG du type de personnalite (16 disponibles). Faible-poly, couleur famille. Toujours visible.
- **Photo** = photo de profil utilisateur. Apparait au unlock/match.
- Les deux peuvent coexister visuellement (carte profil = photo + avatar en accent).

### Carte profil partenaire (format obligatoire)

Ordre verrouille (cf. `feedback_partner_card_format.md`) :

1. Photo (rounded, jamais carre net)
2. Prenom + age
3. Ville
4. Pill personnalite (couleur famille pastel + label type)
5. customTagline en italic Cormorant Garamond
6. Hobbies emoji (les seuls emojis autorises dans l'UI)

---

## Animations & easings

### Easings de reference

| Type | Easing | Duree typique |
|------|--------|---------------|
| Scroll reveal | `cubic-bezier(0.4, 0, 0.2, 1)` | 600-800ms |
| Hover lift / cards | `cubic-bezier(0.34, 1.4, 0.64, 1)` | 250-350ms |
| Icon pop / mini interactions | `cubic-bezier(0.34, 1.6, 0.64, 1)` | 200ms |
| Coverflow / slides physiques | `cubic-bezier(0.4, 0, 0.2, 1)` | 900ms |
| Spring premium / modal entry | spring naturel (Reanimated) | 400-600ms |

### Patterns d'animation valides

- **Scroll reveal** : `IntersectionObserver` + classes `.reveal` / `.is-visible` (opacity + translateY 24px → 0).
- **Hover cards** : `transform: translateY(-4px)` + ombre legere. CSS scoped, jamais Tailwind `hover:translate-*` (conflit avec reveal).
- **Hover boutons** : spring + `will-change: transform` + fleche `translateX` via `.btn-arrow`.
- **Coverflow infini** : tous les items dans le DOM, position via `transform: translateX(calc(-50% + Xpx)) scale(S)`, transition CSS 0.9s.
- **Auto-advance carousels** : minimum 5 secondes par slide. Pas de fleches, pas de dots.
- **LinearTransition Reanimated** : pour les avatars participants qui defilent (8s loop).

### Regles d'animation

- ✅ Fluide ("mousse"), continue, jamais saccadee.
- ✅ Mouvement physique (translate) plutot que fade brutal.
- ✅ Item central grand et opaque, items laterales petits et transparents (coverflow).
- ❌ Pas de fade in/out abrupt qui donne l'impression que ca saute.
- ❌ Pas de changement 3 par 3 ou en blocs. Un par un, en continu.
- ❌ Pas d'animation rapide sur les ceremonies importantes (reveal, paywall). Lent et premium.

---

## Conventions UI

### CTA (Call To Action)

- **Primary CTA** : fond burgundy `#8B2D4A`, texte blanc, Playfair 16-17px. Coins rounded 14-16px.
- **Secondary CTA** : fond blanc, bordure burgundy 1.5px, texte burgundy.
- **Ghost CTA** : juste texte burgundy + chevron, pour actions tertiaires.
- ❌ **Jamais de CTA avec fond colore par categorie** (vert sauge, violet, etc.). Reste burgundy ou blanc.

### Cards

- Fond blanc `#FFFFFF`, ombre tres legere (`0 4px 16px rgba(0,0,0,0.04)`), bordure hairline `#EFE6E9`.
- Coins arrondis 18-22px (premium plus rounded que les coins UI techniques).
- Padding interne 16-24px.
- ❌ Pas de bordures epaisses, pas de coins droits, pas d'ombres dures.

### Pills / badges

- Fond pastel famille (`color + '1A'` ou `bgColor` du data file).
- Texte de la couleur famille.
- Petit padding (4-6px vertical, 10-14px horizontal).
- Coins fully rounded.

### Cadenas (elements verrouilles)

- Style stroke (trait), jamais fill.
- Trait 1.5-2px, couleur muted ou burgundy selon contexte.
- Glassmorphism en fond si supperpose sur image (fond blanc 60% + backdrop-blur 12px).

### Scale / zoom CSS pour reduire un composant

- Utiliser `transform: scale(S)` avec `transform-origin: top center`.
- Compenser l'espace vide avec `margin-bottom: -Ypx`.
- ❌ **Jamais utiliser `max-width` pour reduire** (ca coupe au lieu de scaler).
- ✅ Le zoom CSS est la meilleure approche pour scaler proportionnellement un layout complexe (carte + cercle + carte).

---

## Mobile (Expo / React Native) - regles specifiques

### Dimensions pixel-snap

- ❌ Ne JAMAIS laisser une dimension non arrondie sur un composant calcule depuis un facteur d'echelle.
- ✅ Toujours : `Math.round(value)` + `flexShrink: 0` + width/height explicite.

### NativeWind (Tailwind RN)

- Palette burgundy injectee dans `tailwind.config.js` via les constantes `personality-types.ts`.
- Privilegier les classes utilitaires, mais accepter le style inline pour les valeurs derivees (couleur famille dynamique).

---

## Modaux / popups / bottom sheets

- ❌ **Pas de scroll dans les disclaimers et modaux**. Tout doit tenir sur une page, CTA visible directement.
- ❌ Pas de ScrollView en interieur de modal sauf cas extreme.
- ✅ Si le contenu deborde, REDUIRE le contenu (couper, reformuler, simplifier), pas ajouter de scroll.

---

## Identite par espace produit

### Site web (apps/frontend, Vue 3)

- Fond creme `#FBF9F7`.
- Sections "reveal" sur scroll.
- Hero avec ruby heart anime + tagline Playfair.
- Cards rapport couple : couleur burgundy uniforme (`#8B2D4A`) avec cercle de progression SVG. Jamais de couleurs variables vert/ambre/rouge.

### App mobile (apps/mobile, Expo)

- Background neutre `#FBF9F7` ou blanc selon ecran.
- Tabs : logo Compaatible sur Home, Ionicons `chatbubble-ellipses` sur Messages, Ionicons `person-circle` sur Profile.
- Espace Compaatible : eyebrow "ESPACE COMPAATIBLE" + titre permanent personnalise au prenom.
- Paywall : fond noir pur `#0A0709`. Pas de LinearGradient. Logo ruby heart statique a opacity 0.22.

### Admin panel (apps/admin, React)

- Style plus utilitaire, mais reste sur la palette burgundy.
- Pas de gradients flashy. Sobre.

---

## Pieges a eviter (checklist avant merge)

- [ ] Ai-je hardcode une couleur de famille au lieu d'importer depuis `personality-types.ts` ?
- [ ] Ai-je ajoute un tiret cadratin (`—`, `–`) quelque part ?
- [ ] Mes accents francais sont-ils tous presents ?
- [ ] Mon CTA est-il bien burgundy ou blanc (pas couleur famille) ?
- [ ] Ai-je oublie de fermer une `</div>` apres avoir supprime un wrapper ?
- [ ] Mon animation utilise-t-elle un mouvement physique plutot qu'un fade brutal ?
- [ ] Mon modal scrolle-t-il ? Si oui, je dois reduire le contenu.
- [ ] Ai-je arrondi mes dimensions calculees (mobile) avec `Math.round` ?
- [ ] La photo dans ma carte profil est-elle bien rounded (pas carre net) ?
- [ ] Y a-t-il un cadenas en fill au lieu de stroke quelque part ?

---

## Sources techniques

### Code

- `apps/mobile/data/personality-types.ts` — couleurs des 4 familles + 16 types (mobile)
- `apps/frontend/src/data/personality-types.ts` — equivalent web (1161 lignes, plus detaille)
- `apps/mobile/components/PersonalityCardMobile.tsx` — carte personnalite
- `apps/mobile/components/CompatibilityBreakdown.tsx` — breakdown OCEAN visuel
- `apps/frontend/public/_headers` — CSP et regles fonts

### Memoire

- `project_category_colors.md` — adoucissement avril 2026
- `feedback_design_premium.md` — pas d'elements amateurs
- `feedback_animations.md` — animations fluides et lentes
- `feedback_partner_card_format.md` — format carte profil
- `feedback_avatar_vs_photo.md` — vocabulaire avatar/photo
- `feedback_modaux_pas_de_scroll.md` — pas de scroll dans modaux
- `feedback_rn_pixel_snap.md` — dimensions arrondies

### Marketing

- `Compaatible-skills-main/context.md` — identite produit + regles copywriting (lie a design)

---

## Process de mise a jour de ce fichier

1. Toute introduction d'une nouvelle couleur, font ou pattern visuel doit etre ajoutee ici.
2. Toute revision de la palette doit toucher les 2 sources de verite : DESIGN.md + `personality-types.ts`.
3. Une revue design avant chaque release majeure : verifier que les conventions sont respectees.

---

*Derniere mise a jour : Mai 2026 — v1.0 (extraction depuis CLAUDE.md + memoire)*
