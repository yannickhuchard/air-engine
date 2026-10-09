# Workflows et modèle opératoire - tranche 22

Binding expérimental qualifié sur SQLite et PostgreSQL 18.6, issu de la page 45 du white paper. Le profil air.workflow/0.22 ajoute Workflow, OperatingModel et BusinessRule aux données organisationnelles. Il décrit comment une équipe organise ses fonctions et ses services, sans prétendre exécuter les systèmes métier.

WorkflowStep reçoit un binding air.workflow-step/0.22 : id local, name, function exact et participants Actor exacts. FlowSpec recevra air.workflow-flow/0.22 : id local, source, target et condition textuelle obligatoire. Les listes de pas, flux et points de départ sont des ensembles à identifiants uniques. Les références locales et les fonctions de compensation doivent être résolues ; les cycles sont permis et exposés, sans preuve automatique de terminaison.

OperatingModel référence ses BusinessService, ses workflows, une carte de responsabilités explicite vers Role/OrganizationUnit/AuthorityScope et des politiques de ressources référencées. Dans ce premier binding, les politiques sont des AuthorityScope déclarées ; elles ne remplacent pas le registre capacitaire. OrganizationUnit.operating_model devient disponible avec le nouveau profil. Les baselines organisationnelles historiques restent fermées dans leur profil antérieur.

BusinessRule conserve statement, applicability textuelle, authority URI et VerificationCase exacts. Une expression AIR-Expr facultative est validée par le noyau, avec fermeture de ses littéraux Reference. Le service de lecture n’évalue aucune règle sur des assertions textuelles et n’assimile pas la présence de scénarios à leur exécution.

Le service workflow-inspect prend une baseline exacte et expose pas, flux, responsabilités, règles, cycles et pas inaccessibles depuis les points de départ. Il conserve les limites : conditions non évaluées, terminaison non vérifiée, fonctions et compensations non exécutées. CLI, API et MCP partagent ce calcul pur sous contrôle de toute la baseline.

La recette enrichit les trois dossiers Astéria avec le parcours de réclamation SAV, la préparation d’inspection industrielle et la proposition de révocation IAM. La direction et les équipes restent partagées ou propres au dossier selon leurs références exactes. Les neuf cas métier existants restent NOT_EXECUTED. Aucun service, base ou fournisseur IA supplémentaire n’est imposé.

## Usage

Écrire un fichier JSON contenant baseline avec id, revision et digest exacts, puis exécuter python -m air workflow-inspect request.json. POST /v1/workflow/inspect et MCP air_inspect_workflow appellent le même service. Le rapport conserve les déclarations et les références, request_digest et report_digest. Les graphes indiquent reachable_steps_ignoring_conditions, unreachable_steps, terminal_steps et cycle_detected. Aucun de ces champs ne prouve qu’un parcours sera réalisable ni qu’il terminera.

Le contexte et le rapport sont bornés à 1 MiB. Un Workflow contient 1 à 256 pas, au plus 1024 flux et 64 participants par pas. Les conditions et la politique de terminaison restent textuelles. Les expressions optionnelles de BusinessRule doivent produire Boolean ; leurs littéraux Reference sont résolus dans la baseline. Les règles et leurs VerificationCase restent non exécutés par ce service.

Exécuter scripts/demo_workflow.py après scripts/demo_organization.py. Les trois baselines ont 62 objets, avec une fonction humaine de revue distincte, un modèle opératoire et une règle liée aux cas de vérification existants. Les boucles atelier/IAM sont conservées et détectées ; les trois parcours CLI/API/MCP et les restaurations sont comparés.

## Réception de cette tranche

344 tests passent sur chaque moteur, dont onze cas propres aux workflows. La recette des trois dossiers et DEMO-METIER-1 passent. Les résultats ne qualifient ni l’exécution des fonctions, ni la terminaison des boucles, ni l’efficacité des règles métier déclarées.
