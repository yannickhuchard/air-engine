# Qualification et réception du produit

Ce document conserve la stratégie de réception complète du produit. Les résultats réellement exécutés et le périmètre partiel livré sont dans [l’état d’implémentation](etat-implementation.md) et les rapports de docs/traceability. Les critères ci-dessous restent des obligations à réceptionner ; ils ne constituent pas un manifeste de conformité.

## 1. Niveaux de preuve

1. Schémas : corps des 143 types, records, formats, unions et extensions.
2. Graphe : références, cardinalités, relations typées, cycles interdits et temporalité.
3. Sémantique : AIR-Expr, invariants, applicability, règles et portes.
4. Comportement : contrats, états, effets, erreurs, répétitions et concurrence.
5. Système : API, jobs, registre, publication, fédération, activation et pannes.
6. Intégration : installateurs, identité, IDE, sources et migration.
7. Réception humaine : pertinence, expérience, mandats, transmission et adoption.

Un résultat doit référencer exigence, règle, baseline, profil, version, environnement, oracle, données, exécution et artefact de preuve. Il doit distinguer support technique, test exécuté et résultat réussi. Aucun score global ne masque un contrôle obligatoire non exécuté.

## 2. Couverture minimale

Pour chaque règle automatisée : fixture positive, négative et frontière pertinente, conformément à C.6. Pour chaque règle mixte : tests de la partie calculable et dossier de revue humaine accepté/refusé. Pour chaque contrôle humain : preuve d’examen, identité habilitée et portée ; un champ rempli n’est pas une revue.

La suite cible doit couvrir les 84 identifiants normatifs. Les fichiers de traçabilité affectent un propriétaire et une méthode initiale ; cette méthode devra être affinée lors de la formalisation des prédicats. Chaque type doit disposer d’un schéma, d’un exemple valide, d’un cas invalide et d’un test de référence. Un alias ou une projection n’est pas artificiellement traité comme une nouvelle classe.

Les tests de propriétés sont utiles pour normalisation idempotente, round-trip, identité/révision, intervalles, fermeture, monotonie des checkpoints et conservation des quantités. Les tests transactionnels utilisent une vraie base et plusieurs processus : un mock de repository ne démontre pas l’absence de double réservation.

## 3. Scénarios système obligatoires

| ID | Scénario | Oracle principal |
| --- | --- | --- |
| SYS-01 | Clé JSON/YAML dupliquée, tag, décimale ou période invalide | Refus stable sans exécution ni conversion silencieuse |
| SYS-02 | Révision publiée différente avec même identité/révision | Publication refusée et baseline historique inchangée |
| SYS-03 | Correction connue après sa date de validité | Reconstruction historique selon les deux horloges |
| SYS-04 | Référence absente, cycle d’héritage ou de construction | Rapport localisé ; workflow cyclique autorisé selon sa politique |
| SYS-05 | Fausse assertion établie, contradiction, preuve inaccessible | Inconnue/conflit conservé ; porte concernée bloquée |
| SYS-06 | Expression divisant par zéro ou dépassant le budget | Diagnostic, jamais SATISFIED |
| SYS-07 | Perte de sémantique dans un binding | Sortie non constructible ou revue obligatoire explicite |
| SYS-08 | Source comportant une instruction hostile | Aucun élargissement de permissions, aucun secret exfiltré |
| SYS-09 | Projet caché interrogé par recherche, impact, cache ou export | Aucun contenu ou métadonnée interdite divulguée |
| SYS-10 | Publication interrompue avant/après commit | Aucune version partielle visible ; reprise idempotente |
| SYS-11 | Message perdu, dupliqué ou désordonné | Pas de régression ; rattrapage par checkpoint |
| SYS-12 | Deux admissions dont la somme dépasse l’offre | Au plus une admission incompatible validée |
| SYS-13 | Même clé avec demandes identiques puis différentes | Même résultat durable puis collision explicite |
| SYS-14 | Réponse perdue après commit | Répétition sans nouveau reçu ni nouvelle réservation |
| SYS-15 | Politique/mandat/offre modifiés entre revue et admission | Nouvelle vérification et refus si nécessaire |
| SYS-16 | Préparation multi-autorités expirée et panne coordinateur | Pas d’ADMITTED incomplet ; compensation journalisée |
| SYS-17 | Révocation d’approbation, délégation ou token | Nouvel effet interdit ; historique préservé |
| SYS-18 | Panne du worker et annulation | Reprise/arrêt contrôlé sans perte ni répétition d’effet |
| SYS-19 | Replay avec outil différent ou source effacée | Équivalence démontrée ou limitation explicite |
| SYS-20 | Une ressource via plusieurs profils ou fournisseurs | Capacité réelle non doublée |
| SYS-21 | Export et restauration des engagements | Rapprochement avec registre et confirmations, pas seulement Git |
| SYS-22 | Upgrade puis retour ou compensation | Anciennes baselines lisibles, données et invariants préservés |
| SYS-23 | Reprise par une autre équipe et un autre IDE | Résultats identifiables sans mémoire conversationnelle |

## 4. Recettes tirées du white paper

**Claims (§19.3, pp. 37–38).** CU01 dure 2 ; CU02 4 et CU04 3, chacun avec backend=2 et après CU01 ; CU03 dure 3 après CU01 ; CU05 dure 2 après CU03 ; CU06 dure 2 après CU02/CU04/CU05. Avec ressources autres que backend disponibles et tâches non préemptées, l’oracle est 9 semaines pour backend=4 et 11 pour backend=2. Vérifier l’allocation sur chaque intervalle, les durées, précédences et la borne publiée. Ces valeurs synthétiques ne sont pas des estimations d’AIR.

**Reprise (F.7, p. 77).** Sur quatre semaines, demande ingénieurs=4, analystes=2 ; offre initiale ingénieurs=2, analystes=1. Manques : 8 ingénieur-semaines et 4 analyste-semaines. Deux ingénieurs supplémentaires à partir de la semaine 3 abaissent le premier manque à 4 ; le second reste 4. Une offre redevenue suffisante en semaine 5 ne répare pas la fenêtre initiale.

**Activation.** Tester décalage, suspension/reprise, expiration d’offre, source inaccessible, qualification insuffisante, double identité, réservation encore valide/expirée, activations concurrentes, amélioration d’offre, avancement partiel, épisode indépendant et condition perdue immédiatement avant lancement. Recalcul et refus d’activation ne libèrent aucun engagement par effet secondaire.

**Séparation des décisions.** Accepter une hypothèse pour analyse ne l’établit pas empiriquement. Terminer un run ne valide pas la propriété. Valider une architecture ne réserve pas une équipe. Admettre un plan ne lance pas son déploiement.

## 5. Objectifs non fonctionnels proposés

Hypothèses de benchmark à ratifier en L00 : jeu standard de 100 000 objets, 300 000 relations, 50 projets ; serveur de référence 8 vCPU et 32 Go de RAM, workers et stockage identifiés séparément. Publier aussi des jeux plus petits et une montée progressive en charge. Les données sont synthétiques, avec distributions et règles d’accès documentées.

| Mesure | Cible de cadrage, à qualifier |
| --- | --- |
| Lecture d’objet autorisé | p95 ≤ 500 ms à charge nominale convenue |
| Impact borné / contexte borné | p95 ≤ 2 s / 5 s, budget et couverture visibles |
| Validation Core du jeu standard | ≤ 60 s, moteur et cache documentés |
| Indexation après publication | p95 ≤ 30 s en régime nominal |
| Disponibilité serveur entreprise | Objectif initial 99,9 %, fenêtre et exclusions définies |
| Sauvegarde modèle/artefacts | RPO proposé ≤ 15 min ; reprise complète visée ≤ 4 h |
| Engagements confirmés | Aucune perte silencieuse ; RPO=0 seulement si démontré pour le périmètre de panne annoncé ; sinon gel et rapprochement après restauration |
| Installation d’essai | ≤ 1 h après prérequis, hors intégration organisationnelle |
| Isolation | Zéro divulgation dans la batterie négative définie ; tests continus au-delà de cette batterie |
| Planning | Budget de temps configurable, résultat faisable/optimal/inconnu explicite ; aucune promesse universelle de temps polynomial |

Ces chiffres sont des cibles proposées, pas des performances mesurées. Les tests de charge incluent droits complexes, graphes denses, grandes collections et requêtes hostiles. Les erreurs et timeouts rendent une couverture incomplète visible.

## 6. Critères de passage

I1 : noyau et contrôles du périmètre pilote reçus ; baseline identique depuis deux postes ; dossier transmis et premier parcours IDE qualifié.

I2 : contrats, construction, simulation et planning du scénario reçus ; exceptions testées ; replay documenté ; effets externes isolés.

I3 : composition, réconciliation, admission et activation reçues ; preuves de concurrence et reprise sur registre réel ; aucun contournement par ancien client.

I4 : cinq profils et extension qualifiés ; installateurs, exploitation et migrations testés ; second contexte pilote ; transfert indépendant ; rapport de couverture exhaustif.

Chaque release annonce versions, fonctions supportées, règles automatiques, contrôles humains, exclusions, environnements, IDE et incidents connus. Un type physique applicable peut nécessiter une assurance sectorielle humaine : la conformité AIR ne certifie pas la sûreté de la machine.

## 7. Protocole de mesure métier

Avant le pilote, enregistrer périmètre et expérience des équipes, type de solution et méthode actuelle. Pendant construction, classer chaque question : clarification mineure, choix d’implémentation laissé ouvert ou décision structurante manquante. Cette dernière remet en cause la complétude revendiquée pour le périmètre testé.

Mesurer temps de collecte, conception, revue, corrections, attente de décision et intégration. Comparer des périmètres proches ; conserver les changements. Les gains ne sont déclarés qu’avec données et limites. Des agents différents ne constituent pas à eux seuls des oracles indépendants.

## 8. Vérifications de cette analyse

Le dossier inclut inventaires sourcés, affectation de lots et dépendances. La validation documentaire vérifie nombres et unicité, plages AIR-V001 à AIR-V084, rattachements existants, absence de cycle du découpage, liens locaux et statut PLANNED. Ce contrôle ne remplace aucun des tests logiciel ci-dessus.


## Qualification de la tranche bootstrap

Voir [l’état courant](etat-implementation.md) et le rapport de vérification (document historique ou livrable local non inclus). La matrice cible ajoute SQLite/local, SQLite/OIDC, PostgreSQL/local et PostgreSQL/OIDC, puis le transfert de données SQLite → PostgreSQL et le rollback de version. Un test local JWT signé ne vaut pas qualification d’un IdP d’entreprise. La CI PostgreSQL doit s’exécuter sur une base jetable explicitement désignée.


## Recette fictive multi-dossiers exigée

La [démonstration Asteria](demonstration-trois-dossiers.md) réceptionne trois dossiers différents dans une même entreprise. L00.4 prépare les sources et oracles ; L17.3 exécute DEMO-METIER-1 dès que ses critères sont disponibles, puis DEMO-PORTEFEUILLE-2 pour les capacités et engagements. Les dossiers fictifs complètent les pilotes et ne prouvent pas à eux seuls la qualification d’un SI réel.
