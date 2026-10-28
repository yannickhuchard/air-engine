# Architecture Completion Controller

AIR conserve le travail ; le modèle du client conçoit la solution. Le contrôleur
relie ces deux responsabilités par un état durable, des versions exactes et un
mandat borné. Il ne nécessite pas de fournisseur de modèle, abonnement API,
Node, cloud ou service central supplémentaire.

## Périmètre de cet incrément

Un parcours commence par une baseline, un Scope et des objectifs Goal/Requirement
explicites. Le contrôleur réévalue air_assess_readiness, propose les prochains
travaux et conserve des checkpoints immuables. Son résultat distingue
READY_TO_BUILD, REQUIRES_MORE_DESIGN et BLOCKED_ON_DECISION. Les interruptions,
quotas, changements concurrents et autorisations expirées ont leurs propres
états d'exécution et ne deviennent pas un succès.

Un mandat technique enregistré par une identité authentifiée ayant le droit authorize_design
autorise des types précis, des acteurs, une durée et un nombre de changements.
Il permet de déposer et figer atomiquement un prepared_change dans ce périmètre,
sans approbation répétée de chaque détail. Il ne vaut ni avis métier, ni revue
indépendante, ni acceptation de risque. Les décisions, preuves de
vérification déclarées et changements d'intention exigent une escalade.

Le même identifiant et le dernier checkpoint permettent la reprise dans un
autre client. Chaque écriture exige la version attendue : deux agents ne peuvent
pas avancer silencieusement depuis le même checkpoint. Les écritures et le
checkpoint du changement partagent la même transaction du registre.

## Surfaces livrées

- Services create/read/advance/authorize/apply/stop exposés par API, CLI et MCP.
- Reprise avec état compact, tâches prioritaires, questions et vérifications.
- Skills et configurations pour ChatGPT, Claude Code, Codex, Cursor et Antigravity.
- Vue de suivi dans le site Projet d'architecture.
- Tests locaux d'atomicité, concurrence, droits, idempotence et verdicts.
- Démonstration complète sur fixture et lecture du dossier réel ProxiBot,
  sans inventer ses preuves manquantes ; trois parcours Asteria.

Le client garde la maîtrise de son temps d'exécution et de ses approbations.
Un plugin ne garantit pas qu'un modèle continue après fermeture de la session.
AIR rend la reprise vérifiable ; il ne contourne pas les limites du client.
Les essais de protocole ne qualifient pas automatiquement un client natif.

## Parcours de l’architecte

Demander au client connecté :

> Utilise AIR pour compléter ce dossier dans son périmètre actuel. Crée un
> parcours de complétion, expose les limites du mandat technique, puis poursuis
> les tâches autorisées jusqu’à READY_TO_BUILD ou jusqu’à une décision qui exige
> mon intervention. Garde les preuves manquantes visibles et un checkpoint de reprise.

Le premier démarrage doit disposer d’une baseline de livraison ou de construction,
d’un Scope possédé et d’au moins un Goal ou Requirement possédé. La création
ne donne aucun mandat. Le responsable d’installation configure séparément le
droit `authorize_design` d’un sujet habilité dans `access-policy.json`. Ne pas
modifier la politique simplement parce que l’agent rencontre un refus.

Exemple de politique à adapter, sans clé ni secret :

```json
{"version":"design-mandate-1","subjects":{
  "urn:identity:architect":{"read":["example.project"],"write":["example.project"],"authorize_design":["example.project"]},
  "urn:identity:agent":{"read":["example.project"],"write":["example.project"]}
}}
```

Une politique explicite remplace les droits par défaut : conserver séparément
les autres sujets et namespaces nécessaires. L’architecte autorise les sujets
exécutants, types, `max_cycles`, `max_objects`, `max_no_progress` et `expires_at`
(au plus 31 jours). Un même sujet peut représenter l’installation locale ; le
registre n’atteste pas qu’un humain est physiquement présent. Les avis humains
exigent toujours leurs services, droits et qualifications propres.

## API, CLI et MCP

Chaque CLI prend un fichier JSON ; les identifiants sont ceux retournés par AIR.
`run` et `checkpoint` sont des références de service `{id,digest}`. Les sources
architecturales ont `{id,revision,digest}`. Les commandes mutantes suivantes
exigent une clé `idempotency_key` stable et le dernier checkpoint.

| CLI | Outil MCP | POST API | Fonction |
| --- | --- | --- | --- |
| `completion-create` | `air_create_completion_run` | `/v1/completion/create` | Épingler baseline, Scope, objectifs et intention |
| `completion-read` | `air_read_completion_run` | `/v1/completion/read` | Réévaluer, reprendre ; aperçu facultatif `prepared_change` |
| `completion-authorize` | `air_authorize_completion_run` | `/v1/completion/authorize` | Mandat explicite, droit `authorize_design` |
| `completion-advance` | `air_advance_completion_run` | `/v1/completion/advance` | CHECKPOINT, ESCALATE, RESOLVE, RESUME, ADOPT_BASELINE |
| `completion-apply` | `air_apply_completion_run` | `/v1/completion/apply` | Déposer et figer atomiquement la proposition admissible |
| `completion-stop` | `air_stop_completion_run` | `/v1/completion/stop` | PAUSED ou CANCELLED ; arrêt possible malgré quota plein |

```text
python -m air --home <home> completion-read <request.json>
```

Lire les tâches prioritaires et les sources par pages. Valider les brouillons,
préparer par `air_rebase_drafts` avec `include_bundle: false`, puis lire l’aperçu
du contrôleur. `air_apply_completion_run` remplace dépôt et fermeture séparés.
CHECKPOINT peut conserver `prepared_change` avant une interruption. La lecture
rend `pending_change` pour reprendre le candidat sans le régénérer ; application
ou adoption d’une nouvelle baseline efface ce pointeur courant, pas son historique.
Un échec du checkpoint annule aussi les objets, la baseline et leurs audits.
Une répétition équivalente ne compte pas comme un nouveau cycle.

Les décisions, risques, acceptations de lacunes, dérogations, budgets, stratégies
fournisseurs, observations présentées comme mesurées, clôtures de projet,
changements d’état épistémique et preuves déclarées exigent l’approbation d’un
`prepared_change` exact dans `approved_prepared`. Une simulation réellement
reproduite par AIR depuis un artefact retenu peut être consignée sous mandat,
sans qualification indépendante inférée. Modifier simultanément ses entrées
empêche cette exception. L’intention du Scope et des objectifs ne peut pas être
réécrite : convenir d’un nouveau parcours.
Un mapping de contrôle PLANNED reste un plan technique autorisable ; VERIFIED,
IMPLEMENTED ou NOT_APPLICABLE requièrent l’approbation exacte. Documenter une
lacune ne l’accepte pas. Effacer une contestation ou résoudre une inconnue ne
peut pas être utilisé comme raccourci pour fermer la porte de connaissance.

ESCALATE conserve une question, son type et ses sources exactes. Les dépendances
déclarées empêchent d’appliquer un changement affecté tant que la question est
ouverte ; les travaux indépendants peuvent continuer. RESOLVE exige un sujet
habilité et conserve sa réponse, sans modifier automatiquement le modèle ni
fermer une porte humaine. Une baseline avancée par un autre contributeur exige
une lecture puis ADOPT_BASELINE explicite, à intention et profils inchangés.

Une réponse n’entraîne aucun envoi externe, achat ou déploiement. La boucle
est bornée à 200 cycles, 10 000 objets écrits, 1 024 checkpoints et 64 questions
par parcours ; les limites opérationnelles existantes s’appliquent aussi.
L’absence de progrès compare les critères de readiness. Une replanification
ou un nouveau mandat est nécessaire après la limite convenue. Une annulation
est définitive ; une pause peut être reprise. Le site exporte au plus 32 parcours
du namespace et signale explicitement une couverture bornée.

## Connecter les clients

`air ide-setup` compile les fichiers avec `client` égal à `claude-code`, `codex`,
`cursor`, `antigravity` ou `chatgpt`. Le mode contribute peut appliquer sous
mandat, mais ne permet pas d’octroyer ce mandat dans la configuration standard.
Pour que l’architecte accorde lui-même ce mandat depuis son client, compiler
avec `design_authority: true` et `access: contribute`, puis utiliser un sujet
ayant déjà le droit serveur `authorize_design`. Cela expose l’outil sans
conférer de droit supplémentaire ; les fichiers Claude et Codex configurent une
demande de confirmation, sous réserve des réglages effectivement chargés du client.
Le profil MCP `auto` conserve les droits réellement annoncés par le serveur ;
un profil restrictif `contribute` doit être remplacé explicitement si l’autorité
doit aussi être visible. Les approbations propres au client restent applicables.
Les configurations ne lisent ni ne recopient le contenu du fichier de jeton.

- Claude Code : `.mcp.json` et skills `.claude/skills` ; [MCP officiel](https://code.claude.com/docs/en/mcp).
- Cursor : `.cursor/mcp.json` et instructions portables ; [configuration officielle](https://prod.cursor.com/help/customization/mcp).
- Antigravity : `.agents/mcp_config.json` par projet ; [configuration officielle](https://www.antigravity.google/docs/mcp).
- ChatGPT : `chatgpt/air-connection.json` décrit les prérequis d’une connexion
  MCP distante autorisée et `chatgpt/AIR-COMPLETION.md` le parcours. Sans adresse
  distante fournie, l’endpoint reste absent. Le client doit autoriser et connecter
  le service ; [contrat MCP OpenAI](https://developers.openai.com/plugins/build/mcp-server).

Les fichiers sont générés depuis les mêmes services et skills. Ils ne prouvent
ni installation native, ni présence dans une marketplace, ni permission du
client pour tous les outils. Un 404 demande un diagnostic ; un 429 demande
une reprise bornée. Ne pas relancer indéfiniment ni affirmer qu’un outil a réussi.
Le moteur ne contient aucun fournisseur de modèle ni ordonnanceur de sessions.
La persistance du dossier n’implique pas celle du raisonnement de l’hôte.

## Suivi dans le dossier

La page `completion.html`, accessible depuis l’accueil et la navigation, expose
les prochains travaux, questions, état d’exécution et références de reprise.
Son JSON est `completion-runs.json`. Il s’agit d’un export figé, sans mutation
depuis le navigateur ni authentification embarquée. Régénérer les livrables
après une évolution du registre. Les critères documentaires, les mandats et
les avis qualifiés restent visibles séparément.
L’état d’autorisation est calculé pour l’identité qui exporte la page. Les
réponses du contrôleur sont limitées à 1 Mio ; les budgets existants de
readiness et des simulations restent applicables.
