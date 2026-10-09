« Le pilote assurance santé » - ce qu’un usage réel a appris à AIR
==================================================================

Un pilote réel a été conduit du 22 septembre 2026 sur deux projets d’architecture de solution, hors de ce dépôt,
contre une installation AIR dédiée. Il a produit 27 constats datés et prouvés ; la [tranche 30](lot-ameliorations-pilote.md)
en corrige 22, dont les quatre bloquants. Ce document dit comment le pilote a été mené, ce qu’il a mesuré, et ce
qui reste ouvert.

## Le pilote

Organisation fictive, aucune donnée réelle. Une instance AIR dédiée, quatre dépôts git, quatre sujets déclarés
(un architecte par projet, un architecte de portefeuille, un opérateur en lecture).

| Dépôt | Contenu | Taille |
| --- | --- | --- |
| Portefeuille | manifeste, politique d’accès installée, charte, index holistique, journal des constats | 21 fichiers |
| Noyau partagé | périmètre d’entreprise, concepts partagés, politique de protection des données de santé | 15 objets |
| Plateforme d’assurance santé | 5 contextes bornés - catalogue produits, vente, gestion des contrats, sinistres, administration -, 7 agrégats, 28 opérations, 11 événements, 2 cycles de vie, un serveur MCP et quatre bancs | 237 objets |
| Gestion de la fraude | 4 contextes sur le cycle détecter, évaluer, agir, escalader ; cycle de vie d’un dossier ; règles de score ; cible temps réel p95 ≤ 2 s | 100 objets |

Les exigences du commanditaire étaient : une description OpenAPI standard par API, des API conçues selon DDD et
MECE, un serveur MCP unique portant quatre bancs, et un système de fraude partagé temps réel.

Deux passes ont été faites avec le **même modèle** : la passe 1 sur AIR 0.29 telle qu’elle existait, la passe 2
sur AIR 0.30 après correction. Chaque écart de la passe 1 a été enregistré par les outils du pilote au lieu
d’être contourné en silence.

## Ce que la passe 1 a mesuré

| Exigence | Résultat en 0.29 |
| --- | --- |
| OpenAPI standard par API | Aucune API ne compilait : chemins à paramètre refusés (18 opérations sur 28), agrégats hors du sous-ensemble plat. Après contournement : 0 paramètre de chemin, 0 réponse d’erreur pour 21 codes déclarés, 29 composants nommés par empreinte, 0 schéma de sécurité, 0 description |
| API DDD | Aucun contexte borné, agrégat, objet-valeur ni carte de contextes en tant que tel ; 7 parties d’agrégat (lignes de sinistre, garanties, membres assurés, montants) non représentables |
| API MECE | Aucun contrôle ; l’équipe a écrit 80 lignes de vérification maison |
| Serveur MCP unique, quatre bancs | Pas de composition de blocs ni de binding MCP : quatre fonctions et des responsabilités en texte |
| Fraude temps réel | Pas de binding asynchrone : les 14 événements sans canal, l’abonnement remplacé par un webhook, la fin conditionnelle du cycle inexprimable |
| Dépendance entre projets | 5 références → 69 objets recopiés, découverts par essais ; l’index du portefeuille qualifiait ensuite ces copies de violation bloquante |

Coût mesuré d’un changement de schéma : 36 schémas modifiés entraînent 37 révisions supplémentaires (13 ports,
11 événements, 8 flux, 5 bindings). `air impact` calcule cette cascade correctement ; rien ne la produit.

## Ce que la passe 2 a mesuré

Même modèle, exprimé avec les capacités de 0.30, sur les mêmes baselines rejouées.

| Mesure | Passe 1 (0.29) | Passe 2 (0.30) |
| --- | --- | --- |
| API de la plateforme compilées | 0 sur 5 | 5 sur 5, valides contre le schéma officiel OpenAPI 3.1 |
| Chemins à paramètre | 0 (18 contournés en `/products/~productId`) | 18 chemins, 20 paramètres de chemin |
| Réponses d’erreur | 0 pour 21 codes déclarés | 49 réponses 4xx/5xx en problem+json |
| Paramètres de requête et d’en-tête | 0 | 29, dont `Idempotency-Key` sur chaque commande |
| Composants nommés par empreinte | 29 | 0 |
| Schémas de sécurité, opérations décrites | 0, 0 | 5, 28 sur 28 |
| Pertes de fidélité enregistrées (plateforme) | 106 | 17 |
| Pertes de fidélité enregistrées (fraude) | 9 | 0 |
| Contrôles DDD/MECE exécutés par AIR | 0 | 10, plus 4 limites déclarées |
| Canal d’événements temps réel | aucun | `claims.events` publié par la plateforme, souscrit par la fraude |
| Fermeture entre projets | 69 objets calculés à la main | 80 calculés par AIR, avec détection d’épingles périmées |
| Index du portefeuille | REVIEW_REQUIRED (copies légitimes jugées bloquantes) | CONSISTENT_AT_PINS, 0 écart bloquant |
| Clone d’équipe sous Windows | 8 conflits, code 1 | 0 conflit, code 0 |

Deux effets utiles, non prévus : la porte de construction, désormais accessible au dossier d’architecture, a
immédiatement relevé 40 manques réels dans le modèle du pilote (effets d’état par opération, justification des
unités) ; et le service de fermeture a révélé que le projet fraude épinglait encore des révisions périmées de la
plateforme.

## Ce que le pilote n’a pas démontré

- Le client Claude Code n’a pas été exécuté ; la suite IDE-01 à IDE-10 n’a pas été passée.
- Aucun système métier n’a été contacté ; les descriptions restent `DRAFT_DESIGN_ONLY`.
- Les scénarios de réception métier ne sont pas exécutés ; la porte de construction reste BLOCKED sur le modèle du pilote.
- L’organisation est fictive et une seule personne a tenu les quatre rôles : rien n’est démontré sur la
  coordination réelle entre équipes.
- Cinq constats restent ouverts, listés dans la [tranche 30](lot-ameliorations-pilote.md).

## Ce que le pilote a appris sur la méthode

1. **Une exigence formulée en une phrase se heurte à une dizaine de limites concrètes.** « Une OpenAPI standard
   par API » a produit six constats distincts, chacun mesurable.
2. **Les constats les plus coûteux ne sont pas les plus visibles.** Le refus des chemins à paramètre se voit tout
   de suite ; la cascade de 73 révisions et la fermeture de 69 objets ne se voient qu’en les faisant.
3. **Deux fonctions d’AIR peuvent se contredire.** La fermeture des baselines impose de recopier les objets d’un
   autre projet, et l’index qualifiait ensuite ces copies de violation. Seul un usage réel montre ce genre de
   contradiction.
4. **Ce qu’un outil ne vérifie pas doit être écrit.** Les contrôles ajoutés disent aussi ce qu’ils ne contrôlent
   pas ; sans cette liste, un rapport « aucune violation » se lit comme une conformité.

## Passes 3 et 4 : le même pilote, travaillé par un agent

AIR est fait pour être travaillé depuis Claude Code ou Codex. La passe 3 a confié cinq demandes d’architecte à des
sessions d’agent qui n’avaient que les dépôts et les outils MCP d’AIR 0.30 ; la passe 4 les a rejouées sur AIR 0.31,
plus un changement de bout en bout côté fraude en suivant les fichiers produits pour Codex. La
[tranche 31](lot-parcours-agent.md) vient de ces deux passes.

| Mesure | Passe 3 (0.30) | Passe 4 (0.31) |
| --- | --- | --- |
| Sessions abouties | 5 sur 5 | 4 sur 6 ; les deux autres partielles, chacune sur un défaut corrigé ensuite |
| Appels MCP journalisés | 110 | 104 |
| Appels échoués | 43, sans motif | 1, avec code et indice |
| Volume renvoyé par AIR | 6,6 Mo | 2,1 Mo |
| Constats | 16 (F28 à F43), tous corrigés en 0.31 | 17 (F44 à F60), 13 corrigés en 0.31, 4 ouverts |

Les agents ont figé deux versions de la plateforme (annulation puis réouverture d’un sinistre) et une version de la
fraude réalignée sur la plateforme, et ont relevé des défauts de conception que les contrôles structurels ne voient
pas : une date de refus jamais enregistrée, une clôture qui éteint un droit de réouverture, un événement sans
l’identifiant dont un autre projet a besoin. Les sessions étaient des agents Claude reliés au serveur MCP par un pont
qui applique les listes d’autorisation du client ; les clients Claude Code et Codex eux-mêmes restent à qualifier.
