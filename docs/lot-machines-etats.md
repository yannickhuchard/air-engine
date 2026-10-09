# Machines à états et replay illustratif - tranche 24

Binding expérimental air.state/0.24 réceptionné dans ce sous-périmètre, à partir de StateMachine (page 45 du white paper). Il ajoute un type DRAFT aux 44 types de données précédents, avec gardes et invariants AIR-Expr booléens. Le schéma SQL reste 6 ; les anciens profils conservent leurs listes de membres et empreintes.

## Modèle

StateSpec air.state-spec/0.24 contient id, name et terminal. TransitionSpec air.transition/0.24 contient id, source, target, trigger, guard et effects. Les identifiants et noms d’entrée sont limités à 64 caractères ASCII ; le déclencheur est une étiquette explicite, sans traduction depuis le texte d’un Event. Les états et transitions ont des identifiants uniques et sont canonicalisés par id. L’état initial et les extrémités sont résolus localement. Un état terminal ne peut déclarer de sortie dans ce binding ; les autres cycles et boucles sur soi-même sont permis.

Les effets sont des déclarations typées avec description ; ils ne sont pas exécutés. L’ordre des invariants et des effets est conservé. Les références littérales des expressions sont fermées dans la baseline. Chaque nom d’entrée doit conserver le même type dans le modèle ; air_state est réservé au moteur et doit être Text lorsqu’il est déclaré.

## Replay

La requête contient baseline et machine exactes, initial_context et une liste de stimuli, chacun avec trigger et context typé. L’état réservé air_state est injecté par le moteur ; l’appelant ne peut le fournir. Les contextes de stimuli sont des snapshots indépendants : les valeurs du contexte initial ou du stimulus précédent ne sont pas reportées implicitement. Les noms inconnus et types incompatibles sont refusés ; une entrée déclarée absente reste UNKNOWN.

Les invariants sont évalués au départ, puis avant et après chaque transition envisagée. Une erreur d’évaluation, un résultat UNKNOWN/CONFLICTING ou une violation d’invariant bloque le replay. La logique AIR-Expr reste inchangée : un OR vrai peut être satisfait malgré une entrée inconnue ; le diagnostic de cette entrée reste conservé. Deux gardes vraies produisent CONFLICTING ; une garde vraie et une candidate inconnue ne permettent pas de choisir. Si aucune garde n’est vraie, il n’y a pas de transition. L’état ne change qu’après validation des invariants sur la cible proposée. La trace distingue proposed_target, target, transition_applied et state_changed : une boucle sur soi-même peut être appliquée sans changement d’état.

Les limites sont partagées sur tout le replay : 50000 étapes AIR-Expr et 512 appels d’expression, invariants compris. Le modèle accepte au plus 128 états, 256 transitions, 32 invariants et 16384 nœuds AST cumulés ; une requête contient au plus 128 stimuli. Requête, contexte exporté et rapport sont chacun bornés à 1 MiB. Les diagnostics de chaque appel sont limités à quatre avec leur nombre total ; la trace ne duplique ni les contextes ni les descriptions d’effets.

## Résultats et usage

state-replay, POST /v1/states/replay et MCP air_replay_state_machine partagent ce calcul pur sous les droits de lecture de toute la baseline. Le rapport expose régime ILLUSTRATIVE, contexte DECLARED_CONTEXTS, état final, trace, coûts, empreintes et nombre de stimuli tentés, consommés et non traités. INPUT_EXHAUSTED n’implique pas un état terminal. Une transition incomplètement contrôlée n’est jamais appliquée, même si sa garde était vraie.

Aucune action externe, autorisation métier ou réception de scénarios réels n’est accordée. Le replay n’est pas une simulation calibrée et ne transforme pas les événements DRAFT en faits. La recette exécutée reprend les trois dossiers Astéria pour confirmation ERP, fraîcheur industrielle et contradiction IAM. Les neuf replays illustratifs sont identiques par CLI/API/MCP et après restauration. Les 391 tests passent sur SQLite et PostgreSQL 18.6 ; voir docs/traceability/verification-state-replay.json.
