# ADR 0039 - Workflows et modèle opératoire déclarés

Statut : accepté pour air.workflow/0.22.

Workflow, OperatingModel et BusinessRule complètent le lien entre équipes, fonctions et services du white paper. Le nouveau profil comporte 38 types de données ; les huit profils précédents et les captures View restent compatibles.

Les pas et flux utilisent des identifiants locaux et des records explicites versionnés. Les références locales sont vérifiées avant conservation, les ensembles sont canonicalisés par identifiant et les références aux fonctions, acteurs et responsabilités sont exactes. Les cycles sont autorisés : une boucle de reprise ne prouve ni erreur ni terminaison. L’analyse signale les cycles et les pas structurellement inaccessibles en ignorant les conditions textuelles ; elle n’exécute aucun parcours.

OperatingModel relie services, workflows, responsabilités et autorités de ressources déclarées. OrganizationUnit peut référencer ce modèle dans le nouveau profil. BusinessRule peut contenir une expression AIR-Expr booléenne validée et fermée sur ses références littérales ; sa présence ne fournit pas de mapping d’observations et ne déclenche aucune évaluation. VerificationCase peut cibler une BusinessRule, sans changer les cas existants.

Le service commun workflow-inspect / API / MCP est un calcul pur borné à 1 MiB de contexte et de rapport. Aucun appel externe, effet de fonction, compensation, qualification métier ou autorisation n’est exécuté. SQLite/local et le schéma SQL 6 restent inchangés.
