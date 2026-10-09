# Utiliser AIR depuis un client MCP

**P04, non publié :** le catalogue courant comprend 78 outils avant filtrage. Stdio et HTTP calculent
le même sous-ensemble selon l'identité et les actions réellement accordées ; ils le revérifient à chaque
appel. Un profil local peut seulement le restreindre. Lire [identités et mandats MCP](lot-identites-mcp.md).
Une connexion partagée porte une identité de service unique, jamais un SSO individuel implicite.

AIR définit 78 outils, dont seul le sous-ensemble autorisé est exposé à la connexion. Parmi les outils de base : air_submit_job, air_get_job, air_cancel_job, air_discover, air_get_context, air_read_context, air_reconcile, air_package_prepare, air_package_publish, air_package_read, air_package_revoke, air_plan, air_simulate, air_capabilities, air_get, air_export_baseline, air_import_drafts, air_freeze_baseline, air_propose_change, air_validate_construction, air_diff, air_impact, air_compile_view. La découverte retourne les schémas JSON stricts. Les outils de packages publient ou révoquent une conception locale avec mandat explicite. Ils ne peuvent admettre ni activer un projet.

## Transport local stdio

Installer et démarrer AIR, puis créer un jeton dédié au rôle reader ou editor. Appliquer au besoin une politique de namespace décrite dans lot-collaboration-projections.md. Le client lance l'interpréteur installé avec les arguments suivants, en remplaçant les chemins par ceux de son installation :

~~~json
{"command":"D:/development/air/.venv/Scripts/python.exe","args":["-m","air.mcp","--home","D:/development/air/.air","--credential","agent.json","--port","8740"]}
~~~

Sur Unix, employer le chemin absolu .venv/bin/python. Cet objet décrit le processus ; le conteneur de configuration varie selon le client. Ne pas écraser une configuration existante. Le raccourci air-mcp est également installé. Aucun secret n'apparaît dans les arguments : le processus lit le fichier privé, puis transmet le jeton uniquement à l'API loopback. L'API réévalue authentification et autorisations à chaque appel.

Le protocole implémenté est MCP 2025-11-25 : initialize, notifications/initialized, ping, tools/list et tools/call. Une ligne UTF-8 par message JSON-RPC ; stdout ne contient que le protocole. Limite d'entrée 1 MiB, sortie de l'API 8 MiB. Pas de batch JSON-RPC, resources, prompts, sampling, tasks ni notifications de changement d'outils. Les erreurs métier reviennent dans isError ; une porte BLOCKED est un résultat de calcul, pas une erreur de transport.

## Streamable HTTP local

Le même service fournit POST http://127.0.0.1:8740/mcp. Il exige Bearer, Content-Type application/json, Accept application/json, text/event-stream et, après initialize, MCP-Protocol-Version: 2025-11-25. Les réponses sont JSON ; une notification acceptée reçoit 202 sans corps. GET et DELETE ne sont pas proposés (405). Le serveur est sans session et n'émet pas de MCP-Session-Id ; identité et version accompagnent chaque requête. Il n'offre pas de flux SSE ni de requêtes serveur vers client.

Les Host et Origin étrangers au listener local sont refusés. Ce binding ne constitue pas encore une exposition distante d'entreprise : TLS, OAuth discovery et politique d'origine publique sont à qualifier séparément. OIDC côté API reste une option indépendante du stockage.

## Qualification et sources

Les tests exécutent découverte, validation des schémas, erreurs, refus d'écriture, révocation, limites de taille, framing du processus stdio et binding HTTP. La recette Asteria reprend une baseline dans une nouvelle session MCP via l'API réelle. Les versions natives de ChatGPT/Codex, Claude, Copilot, Gemini, Antigravity et OpenCode ne sont pas toutes installées ou qualifiées : la présence d'un binding standard n'est pas une preuve de compatibilité client par client.

Contrats consultés : [cycle de vie MCP](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle), [transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [outils](https://modelcontextprotocol.io/specification/2025-11-25/server/tools). Les annotations sont des indications au client, jamais des autorisations.

Les outils air_plan et air_simulate (tranche 06) réalisent des calculs purs, sans réservation
ni validation de système métier. Voir lot-planning-capacitaire.md et lot-experiences-illustratives.md.

## Autorité et engagements locaux

Neuf outils supplémentaires décrivent offres, propositions, revues, admission, lecture, libération et activation. Lire docs/lot-admission-locale.md pour leurs noms et limites. Les mandats capacity/review/admit/activate sont explicites ; aucun approved transmis par un IDE ne les remplace. Une réponse created=false relit un reçu historique et ne constitue pas une nouvelle autorisation. Les jobs de calcul restent sans effets métier.

## Renouvellement et clôture

Six outils ajoutent les transitions renewal-propose/renew et closure-propose/review/revoke/close. Voir docs/lot-renouvellement-cloture.md pour les noms exacts et les schémas MCP. Une clôture déclarée ne prouve pas l’exécution d’un système métier, et la libération reste une opération explicite distincte.

## Observations et comparaisons

Deux outils ajoutent air_runtime_ingest et air_runtime_compare. Le premier conserve des observations DRAFT et un reçu authentifié ; le second calcule un prédicat explicite avec couverture partielle. Voir docs/lot-observations-derive.md. Aucun de ces outils ne collecte un système distant, ne crée de remédiation ou ne qualifie automatiquement une mesure.

## Contributions et décisions

air_whoami retourne l’URI d’identité authentifiée ; air_collaboration_submit dépose un objet DRAFT avec un reçu attribué ; air_collaboration_read relit ce reçu sous les droits actuels. L’identité ne contient aucun jeton. Les outils conservent les limites du profil décrites dans lot-contributions-decisions.md.

## Workbench portable

air_compile_workbench génère un HTML autonome depuis une baseline exacte et autorisée. Il n’intègre aucun jeton ni connexion réseau. Le formulaire prépare une contribution à soumettre ensuite avec air_collaboration_submit ; l’export n’écrit pas dans le registre. Voir lot-workbench-portable.md.

## Cibles des objectifs métier

air_assess_goal_targets évalue les cibles structurées d’un Goal exact sur des observations liées à leurs Metrics exactes. Il partage le service pur de goal-assess et POST /v1/goals/assess. Cette tranche ajoutait le 45e outil ; voir lot-objectifs-services.md pour les limites de population, fenêtre et couverture.

## Transport HTTPS facultatif

L’adaptateur stdio accepte --url https://air.example.org:8740 et --ca-file <ca.pem>. Le client conserve son fichier de jeton protégé et n’a pas besoin de la base du serveur. MCP HTTP est disponible à /mcp sur l’origine TLS déclarée. Les redirections sont refusées et les certificats vérifiés ; voir [la configuration HTTPS](lot-transport-https.md). La qualification protocolaire ne vaut pas qualification native de tous les IDE.

## Dossier de connaissance

air_inspect_knowledge retourne assertions, preuves, prémisses, conflits déclarés et décisions d’une baseline exacte, avec leur validité à as_of. Il n’exécute pas les dérivations et ne promeut aucune conclusion. Cette tranche portait le catalogue à 46 outils ; la tranche artefacts le porte à 49. Voir [inférences et conflits](lot-inferences-conflits.md).

## Pièces jointes - air.artifact/0.18

Trois outils supplémentaires portent le total à 49 : air_import_artifact, air_describe_artifact et air_read_artifact. Les imports et lectures base64 sont limités à 512 KiB ; la CLI binaire accepte 16 MiB. Chaque lecture demande le manifeste exact et les droits courants sur son namespace. Voir [contrat des artefacts](lot-artefacts-preuves.md).

## Vues par audience - air.audience/0.19

air_compile_audience_view reçoit baseline et viewpoint exacts et renvoie le HTML déterministe, son empreinte, source_mapping et context_mapping. La sélection est une aide de lecture ; elle n’accorde aucun droit et n’applique pas de masque de champs. Cette tranche portait le catalogue à 50 outils. Voir [vues par audience](lot-vues-audiences.md).

## Captures historiques - air.view/0.20

air_capture_view conserve atomiquement le View DRAFT, le HTML, les mappings et leur provenance ; air_read_captured_view relit le produit historique sous les droits courants. Cette tranche portait le catalogue à 52 outils. Les lectures d’artefacts capturés exigent aussi la baseline source complète ; le replay ne régénère pas la vue. Voir [vues conservées](lot-vues-conservees.md).

## Organisations et responsabilités - air.organization/0.21

air_inspect_organization retourne les équipes, rôles, acteurs, domaines et autorités déclarées d’une baseline exacte. La fermeture complète des droits est contrôlée ; aucune permission serveur n’est créée depuis le texte. Cette tranche portait le catalogue à 53 outils. Voir [organisations et autorités](lot-organisations-autorites.md).

## Workflows - air.workflow/0.22

air_inspect_workflow retourne workflows, modèles opératoires et règles métier d’une baseline exacte. Les cycles et pas inaccessibles sont calculés en ignorant les conditions ; aucune fonction, compensation ou règle n’est exécutée. Cette tranche portait le catalogue à 54 outils. Voir [workflows et modèle opératoire](lot-workflows-modele-operatoire.md).

## Validation de données - air.data/0.23

air_validate_data contrôle la forme d’un payload de Message ou Event à partir d’une baseline et de manifestes exacts autorisés. Le schéma plat local, les mappings de champs et le payload ont des statuts distincts ; aucun schéma distant n’est chargé. Cette tranche portait le catalogue à 55 outils. Voir [données et messages](lot-donnees-messages.md).

## Machines à états - air.state/0.24

air_replay_state_machine évalue les gardes et invariants d’une machine exacte avec des contextes explicites. Les budgets sont partagés, les transitions ambiguës ou incomplètement contrôlées sont bloquées. Les effets restent déclaratifs. Cette tranche portait le catalogue à 56 outils. Voir [machines à états](lot-machines-etats.md).

## Politiques et contraintes - air.governance/0.25

air_check_policy reçoit une Policy et une baseline exactes, une date et des entrées typées. Il distingue applicabilité, satisfaction des contraintes hard/soft et dérogations déclarées sans effectivité vérifiée. Les textes restent NOT_EXECUTED et aucune autorisation n’est créée. Cette tranche portait le catalogue à 57 outils. Voir [politiques et contrôles](lot-politiques-controles.md).

## Structure d’architecture - air.architecture/0.26

air_inspect_architecture expose blocs, ports, bindings HTTP/JSON, flux, lacunes et livrables d’une baseline exacte entièrement autorisée. Il distingue couverture structurelle d’opérations et compatibilité de comportement non vérifiée. Cette tranche portait le catalogue à 58 outils. Voir [structure d’architecture](lot-structure-architecture.md).

## Compilation OpenAPI - air.openapi-compiler/0.27

air_compile_openapi retourne une description OpenAPI 3.1.1, ses octets UTF-8, empreintes, mappings et pertes à partir d’un binding exact et de schémas locaux autorisés. La sécurité et les comportements restent non implémentés ; aucun endpoint n’est contacté. Cette tranche portait le catalogue à 59 outils. Voir [compilation OpenAPI](lot-compilation-openapi.md).

## Référentiel et atelier client - air.workspace/0.28 et air.ide-adapter/0.28

air_compile_workspace retourne l’arborescence d’un référentiel d’architecture de solution depuis une
spécification déclarée : manifeste, conventions, dossiers par domaine et exemple de politique de namespaces.
Il rapporte la politique effective du sujet authentifié domaine par domaine sans accorder aucun droit.

air_compile_ide_adapter retourne les fichiers d’un client agentique - `claude-code` pour l’instant - avec la
commande du serveur MCP, la liste des outils autorisés et refusés, et une empreinte de source. Aucun jeton
n’est lu ni écrit ; les seize outils engageants sont refusés par la configuration produite.

Les deux outils ne contactent aucun serveur, n’écrivent pas le registre et ne créent aucune autorisation. Cette
tranche portait le catalogue à 61 outils. Voir [référentiel et atelier Claude Code](lot-atelier-claude-code.md).

## Portefeuille de projets - air.portfolio/0.29

air_compile_portfolio retourne le dépôt central d’un portefeuille depuis une déclaration : manifeste, conventions,
politique d’accès installable depuis les sujets déclarés, charte du pilote, requête d’index et une requête
`workspace-init` par projet. Il ne lit pas le registre.

air_index_portfolio compile la vue holistique depuis les baselines épinglées exactement de chaque projet, lues à
travers la politique de l’appelant : fermeture, chaîne de conception, identités partagées en accord ou en
divergence, dépendances entre projets et écarts typés. Un sujet sans lecture sur un projet est refusé pour
l’ensemble. Aucun objet ni droit n’est créé ; une divergence exige une revue. Cette tranche portait le catalogue à
63 outils. Voir [portefeuille de projets et pilote](lot-portefeuille-pilote.md).

## Fermeture de baseline - air.baseline-closure/0.30

air_compute_baseline_closure calcule la fermeture transitive de références exactes dans des baselines épinglées,
lues avec la politique de l’appelant : les membres qu’une baseline dépendante doit contenir, leur répartition par
namespace et par type, les références non résolues et les racines introuvables. Il n’écrit rien et ne crée aucune
baseline. Le catalogue comptait alors 64 outils. Voir [améliorations issues du pilote](lot-ameliorations-pilote.md).

## Parcours agent - air.agent-path/0.31

Six outils en lecture seule - `air_guide`, `air_list_revisions`, `air_browse_baseline`, `air_describe_type`,
`air_validate_drafts` et `air_rebase_drafts` - et deux outils d’écriture - `air_deposit_prepared` et
`air_freeze_prepared` - portent le catalogue à 72. Aucun outil en lecture n’écrit dans le registre ; le rebase garde
seulement, pour son auteur qui a le droit d’écrire, un changement préparé que les deux outils d’écriture déposent puis
figent par son identifiant, sans renvoyer les objets. Les deux transports relaient désormais un refus avec son
code AIR, son message, au plus 50 diagnostics, les références indisponibles et un `hint` ; un texte qui n’est pas un
détail codé d’AIR n’est jamais relayé. Des arguments invalides nomment le champ fautif. Le schéma d’entrée de
`air_import_drafts` ne décrit plus que l’enveloppe ; `air_describe_type` donne le schéma de chaque type. Le serveur
stdio lit le port de `<home>/server.json` quand `--port` est absent. Voir [parcours agent guidé](lot-parcours-agent.md).

## Prêt à construire, simulation et livrables - tranche 32

`air_assess_readiness` et `air_simulate_scenario` (lecture seule), `air_record_simulation` (écriture d’un artefact
de rapport, sans objet déposé) et `air_compile_deliverables` (lecture seule) portent le catalogue à 76 outils.
Voir [le contrat de la tranche](lot-pret-a-construire.md).
