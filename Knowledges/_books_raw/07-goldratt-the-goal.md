---
livre: "The Goal: A Process of Ongoing Improvement"
auteur: "Eliyahu M. Goldratt & Jeff Cox"
annee: 1984
genre: business / Theory of Constraints / management
statut: lu intégralement (sections conceptuelles)
source_lecture: goldratt-the-goal.txt (extrait du PDF)
date_lecture: 2026-05-15
priorite: MOYENNE (pas copywriting direct, utile pour funnel marketing + hooks "système")
---

# The Goal

Roman business sous forme de fiction. Alex Rogo, plant manager d'une usine UniCo en difficulté, a 3 mois pour redresser la situation sinon Bill Peach ferme l'usine. Il croise Jonah, un ancien prof de physique devenu consultant en organisations, qui le guide par questions socratiques pour découvrir la Theory of Constraints (TOC). À la fin, l'usine est sauvée, Alex est promu, et le livre se conclut sur les 5 étapes de l'amélioration continue.

Pour Compaatible, le livre n'est **pas un manuel de copywriting**. C'est une formation déguisée à la **pensée système** : comment un funnel marketing (pageview → cta → test → signup → payment) se comporte exactement comme une chaîne de production, avec ses goulots d'étranglement, ses optima locaux destructeurs, et ses leviers de levier extrême au seul point qui compte. C'est aussi une **mine de hooks Twitter/Reddit** sur le thème "votre problème n'est pas où vous croyez".

## Big Ideas / Concepts centraux

### 1. Le but (Goal) n'est PAS l'efficacité, ni la productivité, ni la qualité. C'est faire de l'argent.

Chapitre 5. Alex passe l'après-midi à lister tous les "buts possibles" : achats économiques, qualité, emploi, technologie, parts de marché... et les élimine un par un. Conclusion :

> "The goal of a manufacturing organization is to make money. And everything else we do is a means to achieve the goal."

Toute action est jugée par rapport au but. Une amélioration "locale" qui ne fait pas avancer le but n'est pas une amélioration.

**Transposition Compaatible** : le but n'est **pas** "avoir un beau site", "avoir un bon score Lighthouse", "avoir un test Big Five plus précis", "obtenir des likes Twitter". Le but est **encaisser des paiements de 9,99€**. Tout le reste est un moyen.

### 2. Les 5 étapes focusing (le cœur de la TOC)

Chapitre 36-37, repris dans l'interview finale. La version corrigée (avec le 5e ajusté) :

```
1. IDENTIFY the system's constraint(s).
2. Decide how to EXPLOIT the system's constraint(s).
3. SUBORDINATE everything else to the above decision.
4. ELEVATE the system's constraint(s).
5. WARNING!!!! If in the previous steps a constraint has been broken,
   go back to step 1, but do not allow INERTIA to cause a system's constraint.
```

Traduction adaptée funnel marketing :

```
1. IDENTIFIER le goulot du funnel (la marche où le plus de monde décroche).
2. EXPLOITER ce goulot (le faire tourner à 100% utile, zéro gaspillage).
3. SUBORDONNER tout le reste à cette décision (les autres étapes
   sont au service du goulot, pas leur propre optimum).
4. ÉLEVER le goulot (augmenter sa capacité par tous les moyens).
5. Si le goulot est cassé, recommencer à 1 ET surtout : ne pas laisser
   l'inertie créer de nouvelles contraintes (politique périmée, KPI obsolète).
```

### 3. Throughput / Inventory / Operating Expense (T / I / OE)

Chapitre 8 et 10. Jonah refuse les définitions comptables classiques et impose trois mesures opérationnelles :

> "Throughput is the rate at which the system generates money through sales."
> "Inventory is all the money that the system has invested in purchasing things which it intends to sell."
> "Operational expense is all the money the system spends in order to turn inventory into throughput."

Point critique du chapitre 8 : "If you produce something, but don't sell it, it's not throughput." Production sans vente = zéro throughput.

L'objectif :

> "Increase throughput while simultaneously reducing both inventory and operating expense."

Lou résume parfaitement : "Each one of those definitions contains the word money. Throughput is the money coming in. Inventory is the money currently inside the system. And operational expense is the money we have to pay out to make throughput happen."

### 4. Bottleneck vs Non-Bottleneck

Chapitre 18.

> "A bottleneck is any resource whose capacity is equal to or less than the demand placed upon it. And a non-bottleneck is any resource whose capacity is greater than the demand placed on it."

Et la phrase qui change tout :

> "An hour lost at a bottleneck is an hour lost for the entire system."

Corollaire (chapitre 19) : le vrai coût d'une heure perdue au goulot n'est pas le coût horaire de la machine, c'est le **coût total de fonctionnement de l'usine divisé par les heures du goulot** (2735$/h dans le livre vs 32.50$ "comptable").

### 5. Local optima vs Global optima (PROBABLEMENT le concept le plus important pour le marketing)

Chapitre 8 (Jonah lance le terme), puis chapitre 25 (rule formulée) :

> "The level of utilization of a non-bottleneck is not determined by its own potential, but by some other constraint in the system."
> "Activating a resource and utilizing a resource are not synonymous."
> "A system of local optimums is not an optimum system at all; it is a very inefficient system."

Faire tourner toutes les machines à 100% (= chaque département cherche son optimum local) **détruit** la performance globale du système. Pourquoi ? Parce que ça accumule de l'inventaire en amont du goulot, ce qui augmente OE, sans augmenter T.

### 6. Dependent events + Statistical fluctuations (la rando des scouts)

Chapitres 13-14. Alex part en rando avec une troupe de scouts et découvre que :
- les **dependent events** (chaque scout dépend du précédent) +
- les **statistical fluctuations** (vitesse variable de chaque scout)

= **accumulation de la lenteur**, jamais accumulation de la rapidité. Parce que tu ne peux dépasser celui devant toi.

> "What's happening isn't an averaging out of the fluctuations in our various speeds, but an accumulation of the fluctuations. And mostly it's an accumulation of slowness because dependency limits the opportunities for higher fluctuations."

C'est exactement ce qui se passe dans un funnel : un mauvais titre en page d'accueil ralentit toute la chaîne d'aval. Tu ne peux pas "rattraper" en aval ce que tu as perdu en amont.

### 7. Herbie = le scout le plus lent, métaphore du goulot

Chapitre 15. Herbie a un énorme sac à dos rempli de bordel inutile (sodas, conserves, pelle militaire). Alex distribue le contenu du sac aux autres scouts (= offload sur les non-goulots) et met Herbie en tête de file. Résultat : la troupe va **deux fois plus vite** et reste groupée.

Trois leçons en une :
- Identifier Herbie (le goulot)
- L'élever (lui enlever du poids = offload)
- Subordonner tout le monde à son rythme (rope = rope, tag = drum)

### 8. Drum-Buffer-Rope (DBR)

Chapitre 26. Sharon propose "un tambour" (drum) : Herbie donne le rythme. Davey propose "une corde" (rope) : tout le monde est attaché. Le buffer apparaît plus tard : protection contre les pannes en amont.

- **Drum** : le goulot impose le tempo de tout le système.
- **Buffer** : un stock de sécurité juste avant le goulot pour qu'il ne soit jamais à sec.
- **Rope** : signal qui tire le matériel depuis l'amont, calé sur le rythme du drum.

### 9. Batch size : couper en deux

Chapitres 27-29. Réduire la taille des batchs sur les non-goulots **réduit le temps de cycle** et augmente le flux global. La logique : process batch (taille de production) ≠ transfer batch (taille de transfert). Un petit transfer batch laisse les pièces arriver plus tôt au goulot.

> "If we cut our batch sizes in half, we also reduce by half the setup time... wait, that's wrong. We REDUCE THE QUEUE."

### 10. Inertia = le piège mortel après une victoire

Chapitre 37. C'est l'avertissement le plus subtil et le plus marketing du livre. Quand le goulot est cassé, l'équipe d'Alex **continue** à appliquer les vieilles règles (tags rouges/verts, stocks de finis) alors que la contrainte a changé. Lou (le contrôleur) lâche cette phrase :

> "Whenever the constraint is broken it changes conditions to the extent that it is very dangerous to extrapolate from the past."

Le 5e step corrigé l'intègre : "do not allow INERTIA to cause a system's constraint."

### 11. Le but final : passer de "constraint physique" à "constraint policy"

Chapitre 40. Lou et Alex réalisent que dans la division (au-dessus de l'usine), les contraintes ne sont **pas** physiques. Elles sont des **politiques** : la comptabilité analytique périmée, les KPI d'efficacité locale, les batch sizes "économiques", les transfer prices.

> "The real constraints, even in our plant, were not the machines, they were the policies."

Les 3 questions de management qui se dessinent à la fin :
1. **What to change?** (quel est le problème de fond ?)
2. **What to change to?** (par quoi le remplacer ?)
3. **How to cause the change?** (comment faire passer le changement sans déclencher de résistance ?)

## Bottlenecks & funnel marketing

Un funnel = une chaîne. Et une chaîne est aussi forte que son maillon le plus faible.

**Funnel Compaatible** : pageview → cta_clicked → test_started → test_completed → results_viewed → signup_completed → app_install → session_join → payment

Imaginons des chiffres bruts (à vérifier avec les vraies données PostHog) :
- pageview : 10 000
- cta_clicked : 2 000 (20%)
- test_started : 1 800 (90%)
- test_completed : 600 (33%) ← **probable bottleneck**
- results_viewed : 580 (97%)
- signup_completed : 200 (34%) ← **probable bottleneck 2**
- payment : 80 (40%)

Si on fait ça, on voit immédiatement que **le test_completed et le signup_completed sont les Herbies du funnel**.

**Application stricte des 5 étapes** :

**Step 1 - IDENTIFY** : Le goulot n'est pas "le plus de chute en volume" (c'est cta_clicked, 8000 personnes perdues). C'est **le maillon dont la capacité limite TOUT le système** = celui dont l'amélioration de +1% donne le plus de paiements en bout. Pour Compaatible, c'est probablement **test_completed** (33%) parce que c'est le pivot émotionnel de l'app.

**Step 2 - EXPLOIT** : Maximiser l'usage du test une fois lancé. Pas de waste. Pas d'abandon évitable. Pas de bug, pas de friction technique. Si quelqu'un a commencé le test, on **se bat pour qu'il finisse**. Email de relance, sauvegarde de progression, encouragement à mi-parcours.

**Step 3 - SUBORDINATE** : Tout le marketing en amont doit être **calibré pour envoyer du trafic qualifié au test**. Pas du trafic à volume (vanity metric). Du trafic prêt à compléter. Si une campagne Twitter ramène 1000 personnes qui abandonnent à 50% du test, elle dégrade le système.

**Step 4 - ELEVATE** : Améliorer la capacité du goulot. Refondre le test, raccourcir, gamifier, ajouter des micro-rewards. Mettre du budget produit sur cette étape, **pas** sur la home.

**Step 5 - Avoid inertia** : Si test_completed passe de 33% à 60%, le goulot **se déplace** vers signup ou payment. Il faut alors **réorienter** toute l'organisation. Et surtout, ne pas continuer à optimiser le test sous prétexte que "c'est ce qu'on a toujours fait".

## Throughput / Inventory / Operating Expense appliqués au marketing

Mapping direct :

| TOC (manufacturing) | Marketing Compaatible |
|---|---|
| Throughput = $ généré par les ventes | $ généré par les paiements de 9,99€ |
| Inventory = $ investi dans ce qu'on veut vendre | Stock de leads, MQL, SQL, abonnés newsletter, comptes créés sans paiement |
| Operating Expense = $ pour transformer inventory en throughput | Budget pubs, abonnement outils (Posthog, Supabase, etc.), salaires, freelance, hosting |

Trois actions = trois mouvements simultanés à viser :

> "Increase throughput while simultaneously reducing both inventory and operating expense."

**Augmenter T** : plus de paiements 9,99€/session.
**Réduire I** : moins d'utilisateurs "coincés" dans le funnel (test commencé non fini, signup sans paiement, app installée sans session, etc.). Ces utilisateurs sont du WIP (work in process) : ils consomment des ressources (emails, notifs, support) sans générer de cash.
**Réduire OE** : optimiser CAC, virer les outils qui ne contribuent pas à T.

Insight clé : **un compte créé sans paiement est de l'INVENTORY, pas du Throughput**. Tant qu'il n'a pas payé, c'est de l'argent investi (acquisition, hosting, emails, sollicitations) qui n'a pas encore été transformé.

> Jonah : "If you produce something, but don't sell it, it's not throughput."

Pareil : si tu génères 100 inscriptions par jour mais zéro paiement, tu n'as pas de Throughput, tu as juste gonflé ton Inventory.

## Local optima vs global optima

Le concept le plus dangereux pour Compaatible. Exemples concrets de **faux optima locaux** qui détruisent le système :

**Exemple 1** : "Notre taux de clic sur la home est passé de 12 à 22% !"
Bien sûr, sauf que ces +10% de trafic test_started n'augmentent **pas** test_completed parce que le goulot est en aval. Tu as juste augmenté ton Inventory (visiteurs coincés au milieu du test) et ton OE (charge serveur).

**Exemple 2** : "On a réduit le CPM Twitter de 30%."
Très bien, mais si ces nouvelles personnes moins chères ne convertissent pas en paiement, tu as juste **plus de volume** au début du funnel et **plus de gaspillage** en aval. Local optimum sur le coût d'acquisition, dégradation du throughput global.

**Exemple 3** : "Le test Big Five est passé de 12 à 20 questions, c'est plus précis !"
Local optimum sur la qualité psychométrique. Global pessimum : test_completed s'effondre, donc throughput s'effondre.

**Exemple 4** : "On a ajouté 5 articles SEO sur le blog cette semaine."
Local optimum sur la production de contenu. Si ces articles ne convertissent pas, **tu fais tourner Herbie sur des pièces qu'on ne vendra jamais**. Voir cette citation parfaite :

> "Make the bottlenecks work only on what will contribute to throughput today... not nine months from now."

**Exemple 5** : "On a obtenu 50K views sur ce tweet viral !"
Et alors ? Si zéro paiement supplémentaire, le tweet a juste augmenté l'activation d'un non-goulot. Activation ≠ utilisation.

> "Activating a resource and utilizing a resource are not synonymous."

## Frameworks transposables au marketing

### Framework 1 : Le "Cost of an hour at the bottleneck"

Chapitre 19. Le vrai coût d'une heure perdue au goulot = Total OE / heures disponibles du goulot.

Pour Compaatible : si ton goulot c'est test_completed, le vrai coût d'1% de baisse du taux de complétion = budget marketing total / nombre de tests complétés. Pas le "coût de la page de test". Ce calcul change toute la priorisation.

### Framework 2 : Q.C. devant le goulot

Chapitre 19. Jonah : "Make sure the bottleneck works only on good parts by weeding out the ones that are defective."

Marketing : **qualifier le trafic AVANT le goulot**. Si test_completed est ton goulot, ne pas envoyer du trafic non qualifié au test. Le filtrage doit se faire **en amont** (ciblage Twitter, copy de la page, micro-engagement avant le test) et non en aval. Un visiteur "défectueux" qui consomme une session de test mais n'achètera jamais = pure perte de capacité goulot.

### Framework 3 : Le buffer devant le goulot

Drum-Buffer-Rope. Le goulot ne doit JAMAIS être à sec.

Marketing : il faut un buffer constant de visiteurs **prêts à entamer le test**. Si le flux d'acquisition s'effondre, le goulot tourne à vide = perte irrécupérable. Pour Compaatible, ça veut dire : ne jamais couper Twitter/Reddit/SEO pendant une refonte de la page test.

### Framework 4 : "Match" les batchs en aval avec le goulot

Chapitre 17. La production de Pete (28 pièces/h variable) feed le robot (25 pièces/h fixe). Quand Pete fait 19, le robot fait 19. Quand Pete fait 32, le robot fait 25. **Le système est limité par le minimum de chaque heure**.

Marketing : si tu fais une campagne d'acquisition par à-coups (gros pic Twitter le lundi, rien jusqu'à vendredi), tu satures puis affames ton goulot. Mieux vaut un flux régulier qu'un pic.

### Framework 5 : "Subordinate everything" = règle d'arbitrage

Quand l'équipe doit choisir entre deux features, deux campagnes, deux posts, deux articles : **celui qui aide le goulot gagne**. Si la feature n'aide pas le maillon faible, elle attendra (ou ne se fera jamais).

### Framework 6 : Inertia audit

Chapitre 37. Tous les 30-60 jours, lister les "règles tacites" actuelles du marketing/produit et se demander : "On l'a mise quand ? Pourquoi ? Est-ce que la contrainte qui la justifiait est toujours là ?"

## Citations marquantes

EN : "Productivity is meaningless unless you know what your goal is."
FR : La productivité ne veut rien dire tant qu'on ne sait pas quel est le but. (Ch. 4)

EN : "A plant in which everyone is working all the time is very inefficient."
FR : Une usine où tout le monde travaille tout le temps est très inefficiente. (Ch. 11)

EN : "An hour lost at a bottleneck is an hour lost for the entire system."
FR : Une heure perdue au goulot est une heure perdue pour le système entier. (Ch. 19)

EN : "The real constraints were not the machines, they were the policies."
FR : Les vraies contraintes n'étaient pas les machines, c'étaient les politiques. (Ch. 40)

EN : "Activating a resource and utilizing a resource are not synonymous."
FR : Activer une ressource et l'utiliser ne sont pas synonymes. (Ch. 25)

EN : "A system of local optimums is not an optimum system at all; it is a very inefficient system."
FR : Un système d'optima locaux n'est pas un système optimal, c'est un système très inefficient. (Ch. 25)

EN : "Increase throughput while simultaneously reducing both inventory and operating expense."
FR : Augmenter le throughput tout en réduisant simultanément l'inventaire et les charges opérationnelles. (Ch. 9)

EN : "What's happening isn't an averaging out of the fluctuations in our various speeds, but an accumulation of the fluctuations."
FR : Ce qui se passe n'est pas une moyenne des fluctuations de vitesse, c'est une accumulation des fluctuations. (Ch. 13)

EN : "If you produce something, but don't sell it, it's not throughput."
FR : Si tu produis quelque chose sans le vendre, ce n'est pas du throughput. (Ch. 8)

EN : "Whenever the constraint is broken it changes conditions to the extent that it is very dangerous to extrapolate from the past."
FR : Quand la contrainte est cassée, les conditions changent à un point tel qu'il est très dangereux d'extrapoler à partir du passé. (Ch. 37)

EN : "Most of the time, your struggle for high efficiencies is taking you in the opposite direction of your goal."
FR : La plupart du temps, ta lutte pour l'efficacité te tire dans la direction opposée à ton but. (Ch. 11)

EN : "Make the bottlenecks work only on what will contribute to throughput today... not nine months from now."
FR : Fais en sorte que les goulots ne travaillent que sur ce qui contribuera au throughput aujourd'hui, pas dans neuf mois. (Ch. 19)

EN : "What are we asking for? For the ability to answer three simple questions: 'what to change?', 'what to change to?', and 'how to cause the change?'"
FR : Que demande-t-on ? La capacité de répondre à trois questions simples : que changer ? par quoi le remplacer ? comment provoquer le changement ? (Ch. 40)

## Exemples / parallèles Compaatible

### Parallèle 1 : Le scout Herbie = le test Big Five
Dans le livre, Alex enlève le poids du sac de Herbie. Pour Compaatible : qu'est-ce qui alourdit le test Big Five aujourd'hui ? Trop de questions ? UI confuse ? Pas de progression visible ? Login obligatoire avant la fin ? Chaque "poids" qu'on enlève = +X% de complétion = +X% de paiements.

### Parallèle 2 : Bill Peach et les robots
Au début du livre, l'usine a installé des robots flambant neufs avec 36% d'efficacité dans un département. Tout le monde célèbre. Sauf que zéro produit en plus n'est sorti. Jonah pose les 3 questions qui tuent : "Vous avez vendu plus ? Licencié quelqu'un ? Réduit l'inventaire ?" Trois non.

Pour Compaatible : on a ajouté X tool (analytics, A/B, attribution, IA...). Trois questions :
- Plus de paiements de 9,99€ ?
- Charge opérationnelle réduite ?
- Stock de "coincés dans le funnel" réduit ?

Si trois non, l'outil n'a **rien** amélioré, peu importe ce que dit le dashboard.

### Parallèle 3 : Stacey et les tags rouges/verts
Stacey met en place un système de priorité (red = pour le goulot, green = autre). Ça marche, jusqu'à ce que ça devienne le NOUVEAU problème quand la contrainte change.

Pour Compaatible : chaque "best practice" qu'on installe aujourd'hui (process, KPI, workflow) deviendra une contrainte demain. Il faut prévoir l'audit.

### Parallèle 4 : Le marché comme contrainte finale
À la fin du livre, le goulot interne est cassé, donc la contrainte devient **le marché** : il n'y a pas assez de commandes pour la capacité disponible. Johnny Jons doit aller chercher des deals.

Pour Compaatible : si on optimise tout le funnel, le goulot devient **l'acquisition** (combien de pageviews qualifiés par jour). C'est là que la machine Twitter/Reddit devient la contrainte critique. C'est exactement la situation actuelle.

### Parallèle 5 : Les 9,99€ comme Throughput unitaire
Dans le livre, chaque pièce de l'oven contribue ~1000$ de throughput. Pour Compaatible : chaque session de 9,99€ = throughput unitaire. La règle "an hour lost at the bottleneck = an hour lost for the system" devient : "an abandoned test_completion = ~9,99€ lost AND not recoverable today."

## Application directe Twitter/Reddit Compaatible

10 hooks "système" inspirés de la TOC, prêts à twister en threads. Format : hook + dev court + angle Compaatible. À adapter (pas de tiret cadratin).

### Hook 1 : "Vous optimisez le mauvais endroit."

> Vous pensez que votre problème de conversion vient de la home.
>
> 99% du temps, c'est faux.
>
> La conversion bloque sur **un seul** maillon du parcours. Si vous n'identifiez pas lequel, vous gaspillez votre énergie sur les autres.
>
> En 1984, un ingénieur israélien a écrit un roman business pour expliquer ça. Goldratt l'appelle "the bottleneck". 5 millions d'exemplaires plus tard, c'est toujours la lecture #1 de tout patron d'usine sérieux.
>
> Voici comment l'appliquer à votre tunnel de vente.
>
> [thread suite]

### Hook 2 : "Plus rapide ≠ plus de revenus."

> J'ai mis 6 mois à comprendre que faire tourner mon équipe à 100% RUINAIT mon chiffre d'affaires.
>
> Chaque membre était occupé.
> Chaque tâche était terminée.
> Et pourtant le revenu stagnait.
>
> Parce qu'il y a une différence brutale entre "occuper" une ressource et "l'utiliser".
>
> Activer ≠ utiliser. (Goldratt, The Goal, 1984)

### Hook 3 : "Le faux optimum local"

> Votre taux de clic est passé de 12% à 22%.
> Bravo.
> Et alors ?
>
> Si en bas du funnel rien n'a bougé, vous avez juste **gonflé l'inventaire** : des visiteurs coincés au milieu, qui ne paient pas, mais qui consomment des emails, des notifs, de la bande passante.
>
> Un système d'optima locaux n'est pas un système optimal. C'est un système qui se mange lui-même.

### Hook 4 : "Le scout le plus lent"

> En randonnée, le rythme de la troupe est dicté par le scout le plus lent.
>
> Ce n'est pas une métaphore.
> C'est une loi mathématique.
>
> Dans un système de tâches dépendantes, la lenteur s'accumule. La vitesse, non.
>
> Votre marketing, c'est une troupe de scouts. Trouvez Herbie.

### Hook 5 : "Si vous produisez sans vendre"

> Un million d'impressions sur Twitter ne vaut rien si personne ne paie.
>
> Goldratt l'a écrit en 1984 : "If you produce something, but don't sell it, it's not throughput."
>
> Production sans vente = inventaire. Pas revenu.
>
> Arrêtez de mesurer les vanity metrics. Mesurez le throughput.

### Hook 6 : "L'heure la plus chère du monde"

> L'heure la plus chère de votre business n'est PAS celle de votre meilleur dev.
>
> C'est l'heure perdue sur votre maillon le plus faible.
>
> Si votre goulot c'est l'onboarding et qu'il est down 1 heure, vous n'avez pas perdu "le coût d'1h d'onboarding".
>
> Vous avez perdu **le coût total de votre boîte sur cette heure-là**, divisé par les heures d'onboarding.
>
> Différence x100. Parfois x1000.

### Hook 7 : "Trois questions"

> Avant d'investir dans un nouvel outil marketing, posez 3 questions à votre futur vous :
>
> 1. Est-ce que ça génère plus de paiements ?
> 2. Est-ce que ça réduit mes utilisateurs coincés ?
> 3. Est-ce que ça réduit mes coûts opérationnels ?
>
> Si trois non : poubelle. Même si tout le monde l'utilise.

### Hook 8 : "Le sac d'Herbie"

> Le scout le plus lent transportait des bouteilles de soda, des conserves, une pelle militaire.
>
> Quand on lui a enlevé tout ça, la troupe entière a doublé de vitesse.
>
> Quel poids inutile votre étape de conversion transporte-t-elle aujourd'hui ?
>
> Trop de questions ? Trop de champs ? Trop de "pourquoi" avant le "comment" ?

### Hook 9 : "L'inertie tue plus que les bugs"

> "Vous avez cassé le goulot. Bravo.
>
> Maintenant le vrai danger commence."
>
> Goldratt prévient : quand la contrainte change, vos vieux réflexes deviennent **eux-mêmes** la nouvelle contrainte.
>
> Audit tous les 60 jours. Sinon, l'organisation finit par bouffer ses propres succès.

### Hook 10 : "Le vrai but"

> Quel est le but de votre boîte ?
>
> "Faire un bon produit." Non.
> "Aider les gens." Non.
> "Croître." Non.
>
> Le but est : **faire de l'argent**. Tout le reste est un moyen.
>
> Le jour où vous l'acceptez, chaque décision devient binaire : ça contribue ou ça ne contribue pas ?
>
> (Goldratt, 1984. Toujours vrai en 2026.)

### Bonus hook (un peu plus copywriting pur)

> J'ai lu un roman business de 1984 hier soir.
>
> Trois mois plus tard, mon SaaS a triplé son MRR.
>
> Voici les 5 étapes que j'ai appliquées au pied de la lettre.
>
> 1. Identifier le goulot.
> 2. L'exploiter à fond.
> 3. Subordonner tout le reste à lui.
> 4. L'élever.
> 5. Recommencer, en éliminant les réflexes périmés.
>
> Si vous gérez une boîte sans connaître ces 5 étapes, vous laissez de l'argent par terre.

## Pièges

### Piège 1 : confondre "occupation" et "utilité"
Le piège central de Goldratt. Une équipe marketing qui tourne à 100% (toutes les cases du sprint cochées) peut produire **zéro throughput** supplémentaire si ses actions ne touchent pas le goulot. Tester la valeur d'une action : "Est-ce que ça augmente les paiements 9,99€ ?" Si pas de réponse claire et chiffrable, c'est du faux travail.

### Piège 2 : croire qu'on peut tout optimiser en parallèle
Non. Il y a **un** goulot à la fois. Optimiser 12 trucs en simultané = optimiser zéro. Subordinate everything else.

### Piège 3 : utiliser des KPI hérités sans audit
Les "tags rouges/verts" qui ont sauvé l'usine deviennent la prison de l'usine 6 mois plus tard. Pour Compaatible : tout KPI installé en 2025 doit être réinterrogé tous les 60 jours. Est-ce qu'il sert encore la contrainte actuelle ?

### Piège 4 : croire que le goulot est forcément technique/produit
Goldratt termine son livre sur cette vérité : **les vraies contraintes sont des politiques**. Pour Compaatible, le goulot peut être :
- une politique pricing (9,99€ trop bas/trop haut)
- une politique d'acquisition (Twitter only)
- une politique de communication (avatars trop larges)
- une politique de mesure (suivre les bonnes métriques)

Ce sont des contraintes invisibles. Plus dangereuses que les bugs.

### Piège 5 : viser la "balanced plant"
Le truc le plus contre-intuitif du livre : essayer d'**équilibrer** la capacité de chaque étape avec la demande **augmente** ton inventory et **réduit** ton throughput. Pourquoi ? Parce que les fluctuations statistiques + les dependent events font que si tout est calibré au plus juste, le premier raté en amont casse toute la chaîne en aval. **Il faut de la marge sur les non-goulots**.

Pour Compaatible : prévoir de la surcapacité sur les non-goulots (hosting, support, dev sprint). Pas sur le goulot, qui doit tourner à fond.

### Piège 6 : la viralité comme but
Les vanity metrics Twitter (likes, RTs, impressions) sont par définition de l'**activation**, pas de l'**utilisation**. Un tweet viral qui ne convertit pas = activation maximale d'un non-goulot. Pertes nettes en OE (notifs, follows à filtrer, DMs à gérer) sans Throughput.

### Piège 7 : optimiser le coût d'acquisition AVANT le goulot
Tant que le goulot existe, baisser le CAC = augmenter le volume au début du funnel = **augmenter l'inventaire coincé** au goulot. Ça empire la situation. Il faut d'abord casser le goulot, ensuite baisser le CAC.

### Piège 8 : confondre process batch et transfer batch
Pas évident pour le marketing mais utile. Tu peux **produire** 50 tweets d'un coup (process batch = 50) et **publier** un par jour (transfer batch = 1). Ça réduit ton "queue" sans réduire ton effort de production. La même logique s'applique à la création de contenu, aux newsletters, aux features.
