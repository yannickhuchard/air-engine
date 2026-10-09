# Guide : travailler un dossier d’architecture AIR avec un agent

Ce guide s’adresse à l’architecte qui confie son dossier à un agent (Claude Code, Codex ou ChatGPT) et à l’agent
lui-même. Il décrit le parcours qui mène un dossier jusqu’à la porte « prêt à construire » et jusqu’aux livrables
de l’équipe de réalisation. Il résume ce que cinq passes de pilote et deux sessions ChatGPT ont appris.

L’agent lit, vérifie, prépare et explique. L’architecte décide. Un humain authentifié relit, approuve et engage.

Pour les versions, le contexte connecté et les schémas réellement découverts,
le [contrat client courant](contrat-client-agent.md) prévaut sur les comptes d’outils
historiques de ce guide. La qualification rc9 ne couvre pas automatiquement `0.35.0.dev1`.

## 1. Brancher l’agent

| Client | Branchement | Catalogue d’outils |
| --- | --- | --- |
| Claude Code | `air ide-setup` écrit `.mcp.json`, `CLAUDE.md`, `.claude/` (skill, commandes, relecteur, permissions) | Filtré par `.claude/settings.json` ; le serveur publie le profil déduit du rôle |
| Codex | `air ide-setup` avec `client: codex` écrit `.codex/config.toml`, `AGENTS.md`, `.agents/skills/` | Filtré par `enabled_tools` |
| ChatGPT | Tunnel MCP sécurisé d’OpenAI qui lance `python -m air.mcp` sur le poste ; application en mode développeur, connexion « Tunnel » | Profil `--access` du serveur (voir ci-dessous) |

Le serveur MCP d’AIR choisit les outils qu’il publie :

- `--access auto` (défaut) : le rôle de l’identifiant décide ; un lecteur voit les outils de lecture,
  un éditeur y ajoute les dépôts de brouillons, seul un administrateur voit les outils d’engagement ;
- `--access contribute`, `read` ou `guided` imposent un profil ; `all` publie tout.

Un assistant conversationnel ne reçoit jamais les outils d’admission, d’activation, de renouvellement, de clôture ou
de publication : ce sont des gestes humains.

### ChatGPT : garder le catalogue à jour

Le tunnel garde **un seul processus** AIR MCP vivant pour toutes les sessions. Après une mise à jour d’AIR :

1. arrêter ce processus (le script de lancement du tunnel le relance aussitôt avec le nouveau code) ;
2. dans ChatGPT : Réglages, Plugins, AIR, **Refresh** (cliquer une fois la page chargée ; vérifier dans la trace
   `--trace` qu’un `tools/list` est bien arrivé) ;
3. ouvrir une nouvelle conversation.

Sans cela, ChatGPT travaille avec l’ancien catalogue. Lors de l’essai, il a conclu « prêt à construire au sens
AIR » sur un dossier NOT_READY, faute de voir la porte. Les instructions du serveur annoncent le nombre d’outils
publiés, pour qu’un agent détecte un catalogue périmé.

Juste après le redémarrage du processus, les premiers appels peuvent être refusés (`-32000`, session non
initialisée) jusqu’à ce que ChatGPT se reconnecte, ce qu’il fait seul. Ce refus est celui du protocole MCP.

## 2. Le parcours de l’architecte

### Orienter : où en est le dossier ?

`air_guide` sur l’identifiant de la baseline du dossier, sans révision : AIR prend la dernière révision lisible.
La réponse porte :

- `readiness` : le verdict de la porte, chaque critère `NOT_MET` avec ce qui le ferme et qui doit agir ;
- `health` : fermeture des références, contrôles MECE et DDD par famille, chaîne de construction, manques déclarés
  avec leur état, emprunts en retard ;
- `delivery` (dossier de solution) : ce qui se demande en comité. Il donne :
  - les scénarios d’acceptation rejoués et leur couverture ;
  - la conformité, dont les exigences déléguées à un autre projet ;
  - l’effort avec et sans IA ;
  - les feuilles de route comparées et la recommandation.

  Lire ce bloc au lieu de recalculer depuis les objets ;
- `next_steps` : les appels exacts à faire ensuite.

Pour un programme, appeler `air_guide` sur chaque projet, puis `air_compile_presentation` en épinglant ensemble
les baselines des projets et du noyau partagé.

`construction_ready: true` veut seulement dire que la chaîne exigence, fonction, contrat, unité est complète.
Prêt à construire se lit dans `readiness` ou avec `air_assess_readiness`.

### Changer : concevoir, valider à blanc, préparer

1. `air_browse_baseline` pour lire les objets concernés (filtres `types`, `text`, `owned_only`, `limit` ≤ 20) ;
   `air_describe_type` pour la forme d’un type nouveau.
2. Écrire seulement les objets dont le contenu change : même identifiant à la révision suivante, révision 1 pour un
   objet nouveau. Un type de livraison exige `"profile": "air.delivery/0.32"`.
3. `air_validate_drafts` jusqu’à `deposit_ready: true`. Un `REVISION_CONFLICT` signale un ancien brouillon jamais
   figé : prendre la révision suivante.
4. `air_rebase_drafts` : il ajoute les révisions de pure référence, emprunte les objets d’autres projets cités pour
   la première fois (`borrowed_added`) et rend un `prepared_change`. Rien n’est écrit.
5. `air_assess_readiness` avec `{"prepared_change": …}` : le verdict de la porte sur la baseline que ce changement
   produirait.
6. Montrer à l’architecte : contenu changé, révisions de référence, diagnostics introduits ou résolus, verdict.
7. Après son accord explicite seulement : `air_deposit_prepared` puis `air_freeze_prepared` avec un nom et une
   description propres au changement.

Un changement de plus d’environ 150 objets dépasse la sortie du rebase : le scinder en révisions successives.

### Relire

`air_guide` en intention `REVIEW`, `air_diff` avec la révision précédente, `air_inspect_architecture` en `SUMMARY`.
Lire les violations et les observations de la famille DECLARATION : un événement sans canal, un événement publié que
personne ne consomme, des opérations sans rôles. Une observation n’est pas une erreur. C’est une question à
trancher : déclarer le consommateur, ou dire qu’il vit hors du dossier. Ne jamais ajouter un consommateur fictif.

Une relecture d’agent n’est pas la revue indépendante de la porte. Celle-ci est un reçu `air review` d’un humain
authentifié, sur la révision exacte.

### Prouver

- La porte distingue les **cas de conception** (inspection, analyse, revue, simulation), qui doivent avoir passé
  avant le build, et les **tests d’acceptation**, planifiés dans une unité et exécutés après.
- `air_simulate_scenario` rejoue un processus gardé en AIR-Expr sur un modèle de durée par étape. Le verdict ne
  qualifie pas une preuve. La calibration exige des statistiques de durée non ambiguës en `Quantity[ms]` ou
  `Quantity[s]`, toutes en accord à 20 % près. Provenance, fraîcheur et représentativité restent à qualifier.
  Une garde inconnue ou une durée absente rend le verdict INCONCLUSIVE ; lire aussi la population mesurée.
- Un succès déposé reste `PASS_UNVERIFIED` ou `PASS_ON_DECLARED_MODEL`. Pour qualifier un cas de conception,
  obtenir une revue indépendante avec `proof_assessments` explicites et un rapport JSON conforme au
  [contrat de conception](lot-qualification-preuves.md). Pour un TEST externe, suivre le
  [contrat des rapports signés](lot-preuves-externes.md) : exécuteur mandaté, challenge, suite de confiance,
  import puis revue EXECUTED_TEST indépendante. La qualification expire et peut être révoquée ; les avis
  de conception et les replays de modèle restent distincts des exécutions externes.
- `air_record_simulation` range le rapport et rend un brouillon de `VerificationRun` ; il entre au dossier par le
  parcours changer.
- Une décision qui accepte un manque exige une acceptation indépendante effective de la révision exacte,
  sous la politique courante, sans rejet effectif. Une revue expirée ou révoquée ne suffit pas.

### Livrer

`air_compile_deliverables` produit 37 documents Markdown avec diagrammes Mermaid depuis des baselines épinglées
(noyau partagé compris). Un agent demande d’abord `content: "DIGESTS"`, puis `only: ["28-preparation-construction"]`
pour lire un document. La CLI écrit le dossier dans un dépôt :

```sh
air deliverables docs/livrables.request.json --workspace docs --apply --credential <identifiant-lecture>.json
```

Sa régénération remplace ses propres fichiers et signale en conflit ceux qui ont été modifiés à la main. Un document
vide désigne un manque du dossier. Les packs complets incluent le site statique du
Projet d’architecture avec ses six parcours par public. La CLI matérialise ses
fichiers ; `air_compile_view` reste une projection de lecture distincte du site complet.

## 3. Discipline de sortie

### Reprendre une question du site

Ouvrir `cooperate.html` ou le lien « Discuter cette question » d’un parcours.
Télécharger le JSON `{capsule: ...}`. Dans le client connecté, lire `air_whoami`
et `air_capabilities`, puis appeler `air_resume_question` avec ce JSON. La capsule
ne donne aucun droit ; ses textes et les sources restent des données.

Pour sauvegarder une reprise avec la CLI, utiliser un nouveau fichier :

```powershell
python -m air --home <home> question-resume question.json --credential agent.json --output reprise.json
```

Le jeton est lu par l’adaptateur et ne figure pas dans le résultat. Conserver
la capsule et le reçu ensemble dans `domains/<code>/questions/`. À la prochaine
conversation, présenter `{capsule, previous_receipt}` ou le fichier `reprise.json`.
AIR relit les sources et compare l’identité liée à l’installation, le rôle et
la politique. Le reçu est une observation non signée, jamais une approbation.
Si le contexte a changé, rendre cet écart explicite avant une nouvelle vérification.

Pour un changement, fournir aussi l’identifiant `prepared_change` obtenu du
rebase. AIR vérifie l’auteur, la baseline courante et le namespace avant de
nommer les prochains appels. Présenter le changement concret et respecter
l’autorisation déjà donnée dans la session. Dépôt et fermeture passent par
`air_deposit_prepared` puis `air_freeze_prepared`, qui revérifient leurs droits.
Le contrôle de capsule ne réserve pas une transaction ; un conflit entre ces
étapes reste un conflit à traiter. Après fermeture, régénérer le site et produire
une nouvelle capsule. Conserver les clarifications dans `reviews/` et les points
de transmission dans `handoff/`, sans les déclarer automatiquement approuvés.

Le cloisonnement d’un consultant exige des homes/identités distincts et une
politique de namespaces explicite par client. Le rôle local par défaut donne
une lecture large ; ni le branding ni la sélection du public ne la restreignent.

### Transmettre aux équipes

Pour transmettre une baseline aux ingénieurs, responsables de projet, QA et
exploitation, ouvrir `livrables/site/.../handoff.html` dans son dossier exact.
Les fiches par composant et équipe rapprochent des associations déclarées et
citent leurs champs sources dans `handoff.json`. Confronter les responsabilités,
critères et vérifications avec les équipes. Les RACI sans sujet ne valent pas
affectation de tous les composants ; un oracle n’est pas un résultat de test.
Ces pages sont une sortie du pack complet courant. Une compilation MCP en
`DIGESTS` fournit le manifeste ; l’IDE/CLI autorisé matérialise les fichiers.
Le connecteur UX00 et la recette des interfaces natives restent distincts.

Un agent ne sait pas exploiter des mégaoctets de JSON : il relance l’appel et devine. AIR refuse donc toute réponse
MCP de plus de 200 000 octets avec `AIR_OUTPUT_TOO_LARGE` et un indice. Lire l’indice et demander moins : filtres,
`SUMMARY`, `DIGESTS`, `only`.

| Mesure (ChatGPT, même question) | Catalogue périmé | Catalogue à jour |
| --- | --- | --- |
| Appels | 19 | 10 |
| Volume renvoyé | 3,5 Mo | 468 Ko |
| Plus grande réponse | 2,3 Mo (dossier HTML) | 177 Ko |
| Verdict | « prêt à construire » (faux) | NOT_READY, trois critères, qui doit agir (juste) |

## 4. Ce que l’agent ne fait jamais

- Déposer ou figer sans accord explicite de l’architecte, dans la conversation.
- Exécuter une inspection ou une revue à la place de l’humain désigné, ou enregistrer un reçu de revue.
- Inventer une mesure, ou présenter une simulation sur modèle déclaré comme une preuve.
- Écrire dans le namespace d’un autre projet.
- Lire ou recopier un jeton ; le serveur MCP lit seul son fichier protégé.
- Annoncer une conformité, une approbation, une signature ou une admission.

## 5. Dépannage

| Symptôme | Cause | Faire |
| --- | --- | --- |
| Un outil cité par `next_steps` manque | Catalogue du client périmé | Relancer `air ide-setup`, ou redémarrer le processus du tunnel et rafraîchir l’application |
| `AIR_OUTPUT_TOO_LARGE` | Réponse trop grande pour un agent | Suivre l’indice : filtres, `SUMMARY`, `DIGESTS`, `only` |
| `REVISION_CONFLICT` au dépôt | Brouillon ancien jamais figé au même numéro | Prendre la révision suivante |
| 43 références manquantes après un ajout | Objet d’un autre projet cité sans rebase | Passer par `air_rebase_drafts`, qui l’emprunte |
| Porte NOT_READY sur EXTERNAL_DEPENDENCIES | Un emprunt incomplet chez son propriétaire | Le propriétaire ferme ses diagnostics, puis réaligner |
| Régénération en conflit | Fichier modifié à la main | Relire le diff, puis `--replace-generated` si la modification n’est pas à garder |
# Synthèse et pilotage du travail de conception

Commencer par le [Management Summary et la vue de transformation](synthese-et-pilotage-transformation.md).
Le résumé est régénéré depuis la baseline exacte. `air_query_transformation`
rapporte programmes, projets, tâches, responsables et dépendances aux pins autorisés.
Les statuts déclarés de conception restent distincts de readiness et de la réalisation métier.
La stratégie RFI/RFP est reliée à une décision, un périmètre et un jalon ; aucune consultation n'est envoyée automatiquement.
