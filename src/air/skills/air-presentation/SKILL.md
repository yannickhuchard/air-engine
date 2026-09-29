---
name: air-presentation
description: "Construire, critiquer ou mettre à jour la présentation de direction d'une architecture de solution AIR (français et anglais), au niveau d'un cabinet de conseil en transformation, pour obtenir une décision ou conclure un accord contractuel. Utiliser quand on demande un deck, un support de comité, une synthèse pour la direction, un pitch de lancement ou la revue d'une présentation existante."
license: Apache-2.0
compatibility: "Fonctionne avec tout agent qui lit les Agent Skills (Claude Code, Claude, ChatGPT, Codex, Cursor, Antigravity, OpenCode, Gemini CLI). Le serveur MCP AIR est recommandé ; à défaut, la CLI `air`."
metadata:
  engine: air.presentation/0.33
  languages: fr en
---

# Présentation de direction d'une architecture de solution

Le but est une décision : faire approuver une feuille de route, un budget et des actions de lancement, puis servir
de support à l'accord contractuel. Le deck se lit seul, sans l'orateur ; chaque titre est une conclusion ; chaque
chiffre vient d'une baseline épinglée d'AIR.

## Règles non négociables

1. **La réponse d'abord** (principe pyramidal de Minto). La deuxième diapositive est la synthèse : ce que l'on
   construit, comment, quand, combien, où l'on en est, et la décision demandée.
2. **Des titres d'action.** Chaque titre est une phrase complète qui affirme une conclusion chiffrée
   (« L'IA agentique réduit l'effort de 38 % pour 14 k€ d'abonnements »), jamais un thème (« Estimation »).
   **Test des titres** : lus à la suite, les titres racontent toute l'histoire.
3. **Un message par diapositive.** Tout ce qui est sur la page prouve le titre ; le reste part en annexe.
4. **Des visuels plutôt que des listes** : histogramme, gantt, matrice, carte de chaleur, schéma de blocs.
5. **Rien d'inventé.** Chiffres, dates, noms et verdicts viennent d'AIR. Une hypothèse est dite hypothèse. Une
   simulation sur modèle déclaré n'est pas une mesure. Une porte `NOT_MET` ou un cas `NOT_EXECUTED` reste tel quel.
   Une date est une **date cible** tant que les estimations sont à calibrer ; une correspondance `PLANNED` est
   « affectée », pas « implémentée » ; une marche de conception n'est pas une recette.
6. **Chaque diapositive cite ses sources** (types d'objets et révision de la baseline) en pied de page.
7. **Se terminer par les décisions**, pas par « Merci » : ce slide reste affiché pendant les questions.
8. **Deux langues** : le même deck en français et en anglais, avec un sélecteur. Les noms d'objets gardent la
   langue dans laquelle ils ont été modélisés.

## Écrire pour un dirigeant qui n’est pas architecte

Le lecteur doit comprendre et décider sans explication orale, et sans être submergé.

- **Des phrases complètes** : sujet, verbe, chiffre, conséquence. Pas de liste de mots-clés, pas de « (s) ».
- **Des mots de métier**, jamais le vocabulaire d’AIR ou d’architecte :

| Éviter | Écrire |
|---|---|
| baseline, révision | version vérifiée du dossier |
| critère de la porte non tenu | validation à obtenir, point de conception à compléter |
| bloc d’architecture, unité de construction | composant applicatif, lot de travaux |
| feuille de route | scénario de réalisation |
| j.h, effort | jours de travail, charge de travail |
| CAPEX, OPEX | investissement, coût de fonctionnement |
| chemin critique | enchaînement qui fixe la date de fin |
| zone de confiance | zone protégée |
| ENF, contrôle | exigence de sécurité ou de conformité |
| simulation sur modèle déclaré | objectif atteint en simulation, à confirmer par des mesures |
| marche de conception | parcours testé sur plan |

- **Les projets par leur nom métier** (`projects` dans la requête), jamais par un code technique.
- **Une ligne « Ce que cela signifie »** sur chaque diapositive qui porte une conséquence.
- **Au plus deux lignes par titre** ; le détail va dans le tableau, la note ou l’annexe.

## Obtenir le deck depuis AIR

1. Épingler les baselines : le projet, ses projets frères et le noyau partagé (`air_list_revisions`,
   `air_browse_baseline`). Toujours des révisions exactes avec leur empreinte.
2. `air_assess_readiness` sur chaque baseline : la porte prêt à construire donne ce qui manque et qui le ferme.
3. `air_compile_presentation` avec `{"title", "title_en", "baselines", "client", "provider", "audience", "projects"}` :
   le plan (outline) revient avec les titres d'action calculés et les sources de chaque diapositive.
   C'est le **ghost deck** : le relire et le faire valider avant tout le reste.
4. Le fichier HTML bilingue est pour les personnes :
   `air presentation requete.json --output deck.html` (touches ← → pour naviguer, `n` pour les notes, `l` pour
   la langue ; impression en PDF au format 16:9).
5. `air_compile_deliverables` (contenu `DIGESTS`, puis `only`) fournit les annexes détaillées si l'auditoire
   demande la preuve : matrice de conformité, scénarios, estimation IA, feuilles de route.

Si le serveur MCP n'est pas disponible, construire le même deck à la main en suivant
[le fil narratif](references/storyline.md) et en tirant chaque chiffre des livrables compilés.

## Trois modes

- **Construire** : clarifier l'auditoire (comité de pilotage, sponsor, signature du contrat), la décision
  attendue et les contraintes ; produire le ghost deck ; le faire valider ; compiler ; critiquer ; livrer.
- **Critiquer** : appliquer la [grille de critique](references/critique.md) et rendre les constats en trois
  niveaux (structure, diapositive, finition), du plus coûteux au plus léger.
- **Mettre à jour** : après un changement de modèle, recompiler depuis les nouvelles baselines, comparer les deux
  plans (titres qui changent de conclusion), puis signaler ce qui change pour la décision.

## Adapter à l'auditoire

| Auditoire | Longueur | Accent |
|---|---|---|
| Comité de pilotage | 16 diapositives | synthèse, état de la porte, feuilles de route, risques, décisions |
| Sponsor exécutif | 10 diapositives | synthèse, état de la porte, valeur, coût, calendrier, décision |
| Signature du contrat | deck complet + annexes | périmètre, livrables, critères d'acceptation, planning, prix, gouvernance |

Pour l'accord contractuel, suivre [la clôture contractuelle](references/closing.md).

## Ce que l'agent ne fait pas

- Il n'approuve, ne signe et n'engage rien : l'engagement est un acte humain authentifié.
- Il n'arrondit pas un verdict : `NOT_READY` reste `NOT_READY`, et la diapositive dit ce qui le ferme.
- Il ne recopie ni jeton, ni identifiant, ni donnée personnelle dans le deck.
