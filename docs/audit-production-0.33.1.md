# Audit d’aptitude à la production - AIR 0.33.1

Date : 25 septembre 2026. Référence examinée : `f8bf3e1c145ee538651c6a6cc32d290bdcd9f9df` (`main`).

**Verdict : AIR n’est pas totalement implémenté et cette version ne peut pas être déclarée prête pour une généralisation en production avec ChatGPT ou Claude.** Elle fournit déjà un atelier utile pour un pilote d’architecture encadré. Des défauts reproduits dans les verdicts de revue, de vérification et de simulation empêchent de s’appuyer sur ses statuts comme preuves de réception.

La complétude du white paper et l’aptitude à la production sont deux critères différents. Un sous-ensemble annoncé d’AIR pourrait être exploité sans implémenter toute la fédération. Il doit néanmoins être correct, qualifié et exploitable dans son périmètre. Le numéro de version, le nombre d’outils et une suite de tests verte ne suffisent pas à établir cela.

## Méthode et limites

Examen du white paper AIR 1.1 (81 pages, SHA-256 `30cb373fb23de83eefa2f1f54ae4d9b3f96715af6ef3ad8553d0355746d5c0b0`), du plan, des catalogues normatifs, de l’état d’implémentation, des contrats de tranches, des rapports de pilote et de qualification, des points d’entrée CLI/API/MCP et des chemins de code de validation, identité, revue, simulation et production des livrables. Comparaison avec la CI du commit exact et reproduction des principaux constats dans des SQLite temporaires.

Il s’agit d’un audit de préparation à la production, pas d’une certification de sécurité ni d’une preuve d’absence de défaut dans chaque ligne. Aucun client ChatGPT ou Claude n’a été piloté pendant cet audit ; leurs essais antérieurs sont identifiés comme tels. Aucun serveur métier, jeton privé, base principale ou configuration cliente existante n’a été modifié. Le code applicatif reste inchangé.

Les preuves synthétiques sont dans le rapport de mesures (document historique ou livrable local non inclus). Les scripts et journaux de cette session sont sous `tmp/audit-production-0331/` (non versionnés).

## 1. Ce qui est réellement livré

- Installation Python, SQLite et authentification locale par défaut ; PostgreSQL et validation de jetons OIDC optionnels et indépendants.
- Révisions immuables, empreintes, baselines fermées, propositions de changement, politiques de namespaces, reçus de revue, historique, sauvegarde/restauration et transfert de registre.
- Services communs CLI, HTTP et MCP ; génération de configurations Claude Code et Codex ; skills et parcours guidés.
- Modèles métier, exigences, contrats, données, workflows, états, contrôles, blocs et ports ; compilation OpenAPI et contrôles structurels.
- Portefeuille sur une instance, analyse des dépendances, simulations sur modèles déclarés, planning limité, admission et activation locales sans action sur les SI externes.
- Parcours de conception, simulations de scénarios, dossier de 37 livrables et présentation bilingue.
- Démonstrations Asteria et pilote assurance santé/fraude. Le pilote décrit une organisation fictive ; une seule personne y a tenu les quatre rôles. Les essais d’agents sont utiles mais ne démontrent pas une adoption par plusieurs équipes indépendantes.

Comptage direct de `core.TYPES` : **86 types persistables**, **14 profils de baseline** et **78 outils MCP**. Parmi ces types, 62 portent un nom du catalogue normatif et 24 sont des types propres à l’implémentation. Ce rapprochement de noms ne constitue pas un taux de conformité ; certains concepts normatifs existent partiellement sous forme de contrats de service.

## 2. Pourquoi l’implémentation n’est pas complète

Le moteur annonce explicitement `air_conformant_profiles: []`, `normative_rules_implemented: []` et un cycle de vie de modèle limité à `DRAFT`. AIR-V003 est déclarée pour des sous-profils seulement. Le catalogue de suivi contient 143 types, 84 règles et 18 opérations : les statuts conservés ne réceptionnent pas l’ensemble. Le backlog conserve 59 sous-tâches en cours et 13 planifiées ; aucun des 18 lots majeurs n’est entièrement réceptionné.

| Dimension du white paper | État constaté | Travail restant pour la cible complète |
| --- | --- | --- |
| Core et connaissance | Schémas et graphes partiels, AIR-Expr borné, provenance, références exactes | Couverture normative complète, états et transitions, qualification des preuves, règles et profils de conformité |
| Construct | Chaîne de conception, contrats, OpenAPI, livrables et contrôles structurels | Qualification sémantique des transformations et réalisations, autres bindings, génération/replay de construction et réception indépendante |
| Simulate | Expériences limitées, scénarios à graine, calibration partielle | Correction des verdicts, calibration correctement typée et sourcée, propagation d’état et synchronisation selon profils, modèles spécialisés et recettes de replay qualifiées |
| Federate | Packages et portefeuille locaux, contextes et comparaison de révisions | Fédération entre autorités, publication distante signée, résolution/lockfile complets, réconciliation sémantique et admission distribuée |
| Operate et activation | Observations, comparaisons et engagements locaux | Rattachement aux instances réelles, actifs durables, connecteurs et collecte, remédiation gouvernée, capacité et activation complètes |
| Workbench | Exports et génération de fichiers | Atelier partagé avec sessions et synchronisation ; réception des parcours multiéquipes |

Les cas de test d’un système métier à construire n’ont pas à être exécutés pour commencer sa conception. En revanche, un objet `VerificationRun` déclaré et un replay de navigation ne prouvent pas l’exécution du système construit. Les termes « prêt à construire », « admis » et « opérationnel » du white paper restent distincts.

## 3. Défauts reproduits qui bloquent une réception de production

### AUD-01 - Une revue rejetée ou devenue inefficace satisfait la porte

**Priorité : bloquante pour l’usage du verdict.**

Dans `readiness.assess_readiness`, la sélection des revues contrôle révision, digest et révocation. Elle n’exige pas `outcome=ACCEPTED`, ne contrôle pas l’expiration et ne réutilise pas la vérification de politique et de mandat de `reviews.read_review`.

Reproductions sur une baseline exacte, avec un auteur et un réviseur distincts :

| Situation | Service de revue | Critère INDEPENDENT_REVIEW |
| --- | --- | --- |
| Revue explicitement rejetée | `REJECTED` | `MET` |
| Politique changée et mandat retiré | `POLICY_CHANGED`, `MANDATE_MISSING` | `MET` |
| Horloge avancée après expiration du reçu | `EXPIRED` | `MET` |

Ce même ensemble de revues peut fermer l’attente de revue des décisions qui acceptent des lacunes. Les autres critères de la baseline de reproduction restent bloquants : le constat ne prétend pas avoir obtenu un `READY_TO_BUILD` global, ni une admission effective.

**Réception attendue :** la porte et le service de lecture de revue doivent partager les mêmes contrôles d’effectivité et de décision ; couvrir rejet, expiration, retrait de mandat, changement de politique et révocation.

Sources : `src/air/readiness.py:383`, `src/air/readiness.py:466`, `src/air/storage.py:329`, `src/air/reviews.py:58`.

### AUD-02 - Une analyse déclarée sans preuve devient VERIFIED

**Priorité : bloquante pour la confiance dans les preuves.**

Un `VerificationRun` DRAFT avec `method=ANALYSIS`, `result=PASS`, `proof_level=ANALYSIS`, un exécutant déclaré et un résumé libre passe la validation sans rapport ni Evidence. Après dépôt et fermeture de baseline, la porte classe le cas `VERIFIED`.

La porte choisit la dernière exécution par date déclarée et lit son niveau de preuve. Elle ne distingue pas ici un résultat émis et conservé par le moteur d’une déclaration éditable de l’architecte ou de son agent.

**Réception attendue :** distinguer résultat déclaré, résultat moteur traçable et preuve revue ; vérifier l’origine, le contexte exact, le rapport et les conditions de qualification avant d’afficher `VERIFIED`. Une inspection humaine peut rester permise, avec son protocole et sa réception explicites.

Sources : `src/air/delivery_schema.py:45`, `src/air/delivery_schema.py:254`, `src/air/readiness.py:393`.

### AUD-03 - La calibration accepte une mesure qui n’est pas une durée

**Priorité : bloquante pour les simulations dites calibrées.**

Une observation valide portant le signal `throughput p95` et la valeur `Quantity[requests]=100` a été déposée dans une baseline fermée. Utilisée pour calibrer quatre étapes de durée `FIXED=100 ms`, elle conduit à `model_qualification=CALIBRATED`, `proof_level=CALIBRATED_SIMULATION` et `verdict=PASS`.

`_observed_ms` reconnaît un libellé de percentile, multiplie les unités terminant par `[s]`, mais traite les autres valeurs numériques comme des millisecondes. Le rattachement sémantique de l’observation à l’étape n’est pas assuré par ce calcul.

**Réception attendue :** imposer une grandeur de durée et une conversion d’unité explicite ; vérifier le signal, l’étape, la fenêtre, la couverture et la qualification de la mesure. Une ressemblance numérique ne calibre pas un modèle.

Sources : `src/air/readiness.py:76`, `src/air/readiness.py:92`.

### AUD-04 - PASS reste possible avec des gardes inconnues

**Priorité : majeure pour la lecture des résultats par un agent.**

Dans un scénario de 2 000 tirages, une classe représentant 70 % du poids a une entrée `UNKNOWN`. Le rapport conserve deux gardes inconnues, mais annonce `PASS` sur les 613 tirages mesurés des autres classes.

Le percentile sur les parcours effectivement mesurés peut être utile. Le défaut est de lui associer un verdict global favorable sans domaine de validité suffisamment contraignant : un agent peut l’interpréter comme la satisfaction du scénario complet.

**Réception attendue :** produire un résultat inconclusif ou explicitement partiel lorsque des parcours concernés restent indécidables ; conserver séparément le résultat conditionnel et sa population, et empêcher sa promotion indue en preuve.

Sources : `src/air/readiness.py:139`, `src/air/readiness.py:164`, `src/air/readiness.py:174`.

### AUD-05 - Des devises différentes sont additionnées sans conversion

**Priorité : majeure pour les estimations et feuilles de route.**

Avec les objets du test de feuille de route, un abonnement agentique passé en USD et une main-d’œuvre laissée en EUR sont acceptés par la validation de schéma. Le calcul retourne `labour_cost=42000`, `subscription=350`, `total_cost=42350`, `currency=EUR` : les 350 USD ont été additionnés aux 42 000 EUR sans taux de change ni refus.

**Réception attendue :** conserver les totaux par devise, ou exiger une conversion explicite, datée et traçable avant de produire un total et une comparaison. Les intitulés de présentation doivent suivre les devises réelles. Ce constat ne concerne pas le tableau CAPEX/OPEX, qui groupe déjà les montants par devise.

Sources : `src/air/delivery_calc.py:68`, `src/air/delivery_calc.py:87`, `src/air/delivery_calc.py:90`.

## 4. Qualification de la version

La [CI du commit examiné](https://github.com/yannickhuchard/air/actions/runs/36028218454) est rouge :

| Environnement | Résultat |
| --- | --- |
| SQLite, Windows, Python 3.11 | Succès |
| SQLite, Windows, Python 3.12 | Succès, 588 tests, 2 avertissements |
| SQLite, Ubuntu, Python 3.11 | Succès |
| SQLite, Ubuntu, Python 3.12 | Succès |
| PostgreSQL 17, Ubuntu, Python 3.12 | 404 tests passent, 184 erreurs de préparation ; `tmp/pytest` absent |

L’erreur PostgreSQL vient de la préparation du répertoire temporaire dans la CI. Elle ne démontre pas une régression du stockage PostgreSQL ; elle empêche de déclarer la suite entièrement reçue sur ce moteur au commit courant. Les anciens résultats PostgreSQL 18.6 ne sont pas automatiquement ceux de 0.33.1.

La suite SQLite a également été relancée localement pendant cet audit : **588 tests passent, 0 échec, 0 erreur, 0 ignoré, 2 avertissements, en 740,51 secondes** (Windows, Python 3.12). Le JUnit et son empreinte figurent dans le rapport de mesures. Une première tentative avait un parent de `--basetemp` absent, dû au lancement de l’audit ; elle est exclue des défauts applicatifs et a été suivie de ce rejeu complet après création du répertoire.

Les contre-exemples AUD-01 à AUD-05 ne sont pas couverts par les assertions de la suite existante. Une suite verte ne les réfute donc pas.

## 5. ChatGPT et Claude : ce qui a été démontré

| Surface | Éléments disponibles | Conclusion |
| --- | --- | --- |
| ChatGPT | Essais réels documentés par tunnel MCP ; guide, porte et demandes de préparation de changement ; corrections après catalogues périmés | Parcours pilote démontré. Qualification de production multiutilisateur et exploitation du tunnel à réaliser |
| Claude Code | Adaptateur généré, processus MCP testé ; sessions d’agents Claude via un pont avec permissions | Intégration préparée et services éprouvés. Suite IDE-01 à IDE-10 dans le vrai client non reçue dans les preuves du dépôt |
| Claude.ai / connecteur distant | Pas de recette AIR spécifique trouvée | Ne pas déduire sa qualification de celle d’un adaptateur Claude Code |

Le générateur et les capabilities annoncent `client_qualified=false`. Les essais de pont MCP et les sessions ChatGPT sont des preuves utiles, mais ne démontrent pas le redémarrage, l’isolation, la révocation, le transfert de poste, les injections dans les sources et la reprise avec chaque version de client retenue.

**Parité des transports à corriger :** un lecteur authentifié interrogeant `/mcp` reçoit les 78 outils, dont l’admission, alors que le profil de lecture stdio en publie 48. Reproduction HTTP locale réussie ; `mcp_http.install` crée une `Session` avec son défaut `all`. Cela ne démontre pas un contournement des autorisations métier, qui restent contrôlées dans les services ; cela contredit la restriction du catalogue promise aux assistants et doit entrer dans la recette distante.

Le tunnel ChatGPT documenté lance un processus AIR avec un fichier d’identifiant. **Ce montage n’établit pas à lui seul une identité AIR différente pour chaque utilisateur ChatGPT.** Un partage de ce processus doit être examiné avant de partager l’application entre architectes : attribution des écritures, namespaces, révocation et séparation auteur/réviseur.

La validation OIDC d’AIR est celle d’un resource server : elle vérifie des JWT et un mapping de sujets. Elle n’est pas à elle seule le parcours OAuth interactif et la découverte nécessaires à une intégration distante complète.

Sources externes consultées le 25 septembre 2026 :

- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) : connexion privée possible sans publication directe du serveur ; les messages et résultats sont relayés via OpenAI. Serveur privé ne signifie pas données non transmises au fournisseur.
- [Authentification des plugins OpenAI](https://developers.openai.com/plugins/build/auth) : pour l’authentification utilisateur distante, flux OAuth 2.1, découverte et vérifications côté serveur.
- [MCP dans Claude Code](https://code.claude.com/docs/en/mcp) : processus locaux stdio et transports distants ; surface distincte de Claude.ai.
- [Connecteurs distants Claude](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) : appels depuis l’infrastructure Anthropic, pas depuis le poste de l’utilisateur.

## 6. Exploitation, distribution et documentation

**Livrable présenté comme autonome mais dépendant du réseau.** `presentation.render` charge Google Fonts et Mermaid depuis `cdn.jsdelivr.net/npm/mermaid@11/…`. Le JavaScript Mermaid n’est pas figé à une version exacte ni livré dans le HTML. Le deck conserve son texte hors ligne, mais le rendu des diagrammes dépend du réseau et d’un composant distant. Cela contredit une promesse d’autonomie complète et doit être réglé pour les environnements fermés. Source : `src/air/presentation.py:700`.

**Documentation désynchronisée.** L’état courant annonce encore 60 types et 489 tests, alors que le code en expose 86 et la CI en collecte 588. Le guide d’installation indique 0.29 ; le guide de distribution montre une roue 0.33.0 ; la matrice IDE mélange des états antérieurs. `capabilities.not_implemented` conserve `calibrated-simulation` alors qu’un mécanisme partiel existe. Le registre des constats conserve aussi des éléments ultérieurement traités. Ces incohérences sont particulièrement gênantes pour un IDE censé installer et utiliser AIR en lisant la documentation.

**Exploitation non reçue au périmètre entreprise.** Sauvegarde, restauration, TLS, ACL et jobs ont du code et des tests. Les documents ne fournissent pas une réception actuelle des volumes et latences cibles, des objectifs de reprise, de la supervision et des alertes, de la rétention, d’un IdP réel, ni d’une exploitation par une seconde équipe indépendante. Une configuration de production doit préciser ces engagements à l’échelle visée, sans imposer artificiellement PostgreSQL ou OIDC à un petit déploiement local.

**Distribution actuelle à qualifier.** Les rapports de qualification d’archive présents vont jusqu’à 0.29. Le constructeur d’archives annonce `PRIVATE_PREVIEW` et `license_status=NOT_ASSIGNED`. Les skills embarqués mentionnent une licence qui ne règle pas à elle seule celle du produit. Il manque une distribution 0.33.1 figée, reçue depuis un environnement neuf, avec sa politique de mise à jour et de support explicite.

## 7. Conditions concrètes de passage

1. **Corriger les verdicts et calculs avant d’élargir le périmètre.** Fermer AUD-01 à AUD-05 avec contre-tests ; préserver la différence entre déclaration, analyse, simulation calibrée, test exécuté et approbation effective, ainsi que les unités et devises.
2. **Recevoir une version précise.** CI SQLite/PostgreSQL entièrement verte, installation neuve, mise à jour et restauration ; réconcilier README, capabilities, matrice de compatibilité, catalogues et release.
3. **Qualifier les deux parcours utilisateurs.** Sur les vrais clients ChatGPT et Claude Code retenus, avec plusieurs architectes distincts : lecture, proposition, dépôt autorisé, refus hors périmètre, revue indépendante, révocation, reprise et changement de client sans historique de conversation. Ajouter une recette propre à Claude.ai si cette surface est visée.
4. **Fermer l’exploitation du périmètre retenu.** Identités individuelles, politiques de données, sauvegarde et exercice de restauration, supervision, limites de charge, support et distribution. SQLite/local peut rester le mode initial ; PostgreSQL/OIDC se qualifient lorsqu’ils sont retenus.
5. **Faire réceptionner le pilote par des utilisateurs indépendants.** Trois dossiers crédibles dans une entreprise commune, puis une équipe qui installe et utilise AIR depuis la documentation sans intervention de son développeur. Mesurer les omissions, erreurs et coûts de reprise.

Ces conditions peuvent rendre un **périmètre de conception annoncé** apte à la production. La promesse **AIR complet selon le white paper** exige ensuite la réception des profils, opérations et obligations restantes du plan ; elle ne découle pas de la seule correction de ces défauts.

## Décision d’usage à cette date

- Formation, démonstration et pilote de conception avec revue humaine : **possible**.
- Usage quotidien limité comme aide à la modélisation et à la rédaction : **à encadrer**, sans prendre les statuts de preuve ou de préparation pour des décisions fiables tant que les défauts sont ouverts.
- Généralisation de production, conformité AIR complète, autorité de réception ou engagement automatique : **non reçu**.
