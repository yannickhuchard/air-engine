# Parcours agent guidé - tranche 31

AIR est fait pour être travaillé depuis un agent de développement, Claude Code ou Codex : l’agent lit le dossier,
modifie le graphe et produit les livrables pour l’architecte, qui décide. La passe 3 du pilote assurance santé a
confié cinq demandes d’architecte à des sessions d’agent qui n’avaient que les dépôts et les outils MCP. Les cinq
ont abouti, mais 42 des 110 appels journalisés ont échoué, tous sur un code nu, et chaque session a dû écrire des
scripts pour lire des sorties trop grandes ou construire une cascade de révisions. Seize constats (F28 à F43) et
quatre défauts relevés par la revue de la tranche 30 sont traités ici.

## Ce que l’architecte obtient

Un agent n’a plus à deviner l’état ni à programmer pour modifier le dossier :

1. **Où en est le dossier ?** `air_guide` prend l’identifiant de baseline du dossier et, sans révision, la dernière
   révision lisible. Il rend la version exacte, le contenu possédé et emprunté, les contrôles par famille, les
   blocages de construction groupés et expliqués, les manques déclarés, les objets empruntés qui ont une révision plus
   récente, et les prochains appels exacts pour l’intention demandée : `ORIENT`, `CHANGE`, `REVIEW`, `IMPACT` ou
   `DELIVER`.
2. **Lire sans tout exporter.** `air_browse_baseline` pagine une baseline : comptes par type, puis un sommaire filtré
   par type, identifiant, namespace ou texte ; `FULL` rend les corps, `schemas` insère les fichiers de schéma.
3. **Écrire juste du premier coup.** `air_describe_type` rend le schéma d’un type, un squelette et ses champs de
   référence ; le schéma d’entrée de `air_import_drafts` passe de 191 Ko à moins de 4 Ko.
4. **Valider à blanc.** `air_validate_drafts` n’enregistre rien : schéma, droit d’écriture par namespace, conflit
   de révision, chaque référence résolue dans le lot ou le registre, références en retard ; avec une baseline de base,
   la baseline candidate : dépendants périmés, fermeture, contrôles d’architecture et diagnostics de construction
   introduits ou résolus par le changement.
5. **Compléter le changement.** `air_rebase_drafts` n’écrit aucun objet dans le registre : chaque membre qui pointe
   vers un objet remplacé reçoit sa révision suivante avec des références avancées, jusqu’au point fixe. Il rend le
   lot complet et la `baseline_request` de la révision suivante. Une référence qu’il ne sait
   pas atteindre est rapportée, jamais devinée.
6. **Déposer et figer** restent deux appels explicites, après accord de l’architecte. Le rebase garde le lot sous
   un identifiant `prepared_change`, réservé à son auteur et seulement si celui-ci peut écrire dans le namespace :
   `air_deposit_prepared` puis `air_freeze_prepared` (avec un nom et une description propres à ce changement) évitent
   de renvoyer un lot de 100 Ko, que le modèle devrait sinon réécrire. `baseline_request` prend la provenance des
   brouillons, et `fields_to_review` rappelle de nommer la nouvelle révision.

`air_list_revisions` donne les révisions d’un identifiant, avec pour une baseline son nom, sa description, son
auteur, ses membres, ses parents et les reçus de revue authentifiés qui la visent, révoqués ou non.

## Travailler entre projets

Un projet qui emprunte des objets d’un autre se réaligne en un appel : `air_rebase_drafts` avec
`realign_borrowed: true` prend la dernière révision lisible de chaque emprunt et sa fermeture, puis fait avancer les
objets du projet qui les citent. Il ne crée jamais de révision dans l’espace de l’autre projet : un emprunt qu’il
faudrait réviser là-bas est rendu dans `borrowed_conflicts`. Une révision empruntée déjà enregistrée à l’identique
se dépose avec le seul droit de lecture : le dépôt n’écrit rien dans l’autre espace, et la validation à blanc la
compte comme un réalignement, pas comme une écriture interdite. `air_guide` dit, par espace emprunté, à quelle
baseline du projet propriétaire les emprunts correspondent (`borrowed_alignment`).

## Refus lisibles

- Les deux transports MCP relaient le code AIR, le message, jusqu’à 50 diagnostics, les références indisponibles
  et un `hint` qui dit quoi faire. Un texte qui n’est pas un détail codé d’AIR n’est jamais relayé.
- Une révision absente répond `AIR_NOT_FOUND` (404) pour `air_get` comme pour `air_export_baseline`, avec la
  dernière révision quand le namespace est lisible ; rien n’est révélé sinon.
- Des arguments invalides nomment le champ et la raison.
- Une référence d’artefact prise dans un DataSchema ou une Source ouvre l’artefact : l’empreinte du contenu est
  acceptée comme celle du manifeste.
- `AIR_CONTRACT_EFFECTS` et `AIR_CONTRACT_ERRORS` nomment l’opération, la fonction et ce qui manque.
- Une expression invalide nomme la transition ou l’invariant ; `air_describe_type` publie les opérateurs AIR-Expr et
  leur arité pour les types qui portent des expressions.
- Avant rebase, la validation à blanc dit que les écarts de construction ne sont pas comparables, plutôt que de lister
  comme « résolus » des diagnostics qui ne le sont pas.
- Une réponse trop grande est refusée sous `AIR_OUTPUT_TOO_LARGE`, avec sa taille et la façon de réduire la demande.
- Une date d’enregistrement postérieure à l’heure du serveur est signalée par la validation à blanc.
- L’export et la porte de construction disent ce qu’ils ont vérifié et ce qu’ils n’ont pas vérifié ; deux verdicts
  « valide » ne se contredisent plus en apparence.

## Contrôles nommés d’après leur principe

`air.architecture-checks/0.31` range chaque contrôle dans une famille : **EXCLUSIVITY** (MECE, mutuellement
exclusif), **EXHAUSTIVENESS** (MECE, collectivement exhaustif), **CONTEXT_COHERENCE** (DDD, contexte borné et
propriétaire d’agrégat), **COMPILABILITY**. L’inspection accepte `detail: "SUMMARY"`.

Corrections issues de la revue de la tranche 30 :

- une baseline dont le namespace ne possède aucun membre rend `NOTHING_OWNED`, plus une absence de violation ;
- deux routes qui ne diffèrent que par le nom de paramètre, ou un paramètre répété dans une route, sont refusées ;
- un point d’accès de courtier doit être une URI sans identifiants, requête ni fragment ;
- un fichier de schéma est lu une fois par inspection, quel que soit le nombre de mappings qui le citent.

La famille **DECLARATION** observe les opérations sans rôle déclaré et les événements portés par aucun canal.

`air.http-json-mapping/0.30` accepte `authorization_roles` par opération ; l’OpenAPI les porte dans l’exigence
de sécurité de l’opération et dans `x-air-authorization-roles`. Rien n’est vérifié. Plusieurs erreurs d’une même
opération sur un même statut ne s’écrasent plus : la réponse les liste toutes (`x-air-error-codes`, `oneOf` quand les
schémas diffèrent) et la perte `ERROR_STATUS_SHARED` le dit.

Le rejeu d’une machine à états accepte `start_state` et `continue_on_refusal`, et rend `trigger_sources` : une
propriété « seulement depuis tel état » se prouve en un appel ; un résultat inconnu n’arrête plus la suite quand on
le demande. Le constat F18 du pilote est clos.

La relecture guidée (`REVIEW`) nomme exactement la révision parente et donne ce que le changement a introduit ou résolu
par rapport à elle, en contrôles d’architecture comme en construction. `air_diff` dit quelles propriétés d’un fichier
de schéma ont été ajoutées, retirées ou modifiées.

## Diff et portefeuille

- `air_diff` distingue les remplacements `CONTENT` des `REFERENCE_ONLY`, résume les deux comptes, et compare les
  listes d’enregistrements par leur clé (`name`, `code`, `operation`, `id`).
- L’index de portefeuille liste les manques déclarés par chaque projet et marque ceux qui touchent un autre dépôt,
  signale les objets empruntés plus anciens que l’épingle de leur propriétaire, compte les objets référençants à côté
  des références, et accepte `content: "DIGESTS"` pour ne rendre que les empreintes des fichiers. Ses deux fichiers
  ont droit à 2 Mio chacun, et son moteur passe en `air.portfolio/0.31` : un changement de format se distingue d’un
  changement de données.

## Claude Code et Codex

`air.ide-adapter/0.31` rend un même jeu de parcours guidés pour les deux clients :

| Parcours | Ce qu’il fait |
| --- | --- |
| `air-dossier` | état exact, santé et prochaines étapes |
| `air-proposer` | changement validé à blanc, complété, montré, puis déposé et figé après accord |
| `air-relire` | relecture de la dernière version : différences de contenu, familles de contrôles, construction, rejeux |
| `air-impact` | effet du changement d’un autre projet et réalignement |
| `air-livrer` | descriptions OpenAPI et dossier HTML |

- **Claude Code** : `.mcp.json`, `CLAUDE.md`, `.claude/settings.json`, un skill, cinq commandes, un sous-agent de
  relecture et le manifeste `.claude/air-adapter.json`.
- **Codex** : `.codex/config.toml` (`enabled_tools`, `approval_mode = "prompt"` sur chaque outil d’écriture),
  une section AIR dans `AGENTS.md`, un skill par parcours sous `.agents/skills/` et `.codex/air-adapter.json`.
  Codex ne charge la configuration que pour un projet approuvé et n’a pas de refus de lecture par chemin ; ces deux
  limites sont écrites dans le rapport.

Une régénération après montée de version met à jour sans conflit un fichier encore identique à la génération
précédente, grâce au manifeste ; un fichier modifié localement reste un conflit, et `--apply` n’écrit alors
rien plutôt que d’appliquer une partie. Une section AIR est ajoutée en fin d’un fichier d’instructions qui n’en a
pas, sans toucher les lignes existantes. `air_capabilities` rend `engine_version`, que les instructions comparent
au manifeste pour signaler une configuration périmée.

Le serveur MCP stdio prend le port de `<home>/server.json` quand `--port` est absent.

## Ce qui reste ouvert

| Sujet | Raison |
| --- | --- |
| Suite IDE-01 à IDE-10 avec les vrais clients | Recette native rc9 et essais partiels Codex disponibles ; les blocages et la réception complète restent suivis dans [P07](lot-clients-natifs.md) |
| Constats F06, F16, F17, F23 | Identifiants, notions DDD, serveur MCP et bancs, conditions de workflow : inchangés depuis la tranche 30 |
| Génération AsyncAPI | Le canal est déclaré et contrôlé ; la description reste à produire |
| Rejeu et simulation sur des brouillons | La validation à blanc couvre schéma, références, fermeture, contrôles et construction ; le rejeu et la simulation exigent des objets enregistrés |
| Fichier de schéma en brouillon | Un nouveau DataSchema exige d’importer son fichier, ce qui est une écriture ; la validation à blanc d’un contenu en ligne reste à faire |
| Fonction interne | Un consommateur d’événements ne peut pas être déclaré interne : `AIR_FUNCTION_CONTRACT` reste levé |
| Donnée lue par une garde et écrite par aucun effet | La relecture de la passe 4 l’a trouvée à la main (date de refus jamais enregistrée) ; aucun contrôle ne la détecte |

Aucune conformité AIR complète n’est revendiquée ; aucun des nouveaux services n’écrit dans le registre.
