# ADR 42 - Politiques déclarées et diagnostic explicite

Décision du 20 septembre 2026 : le binding expérimental air.governance/0.25 ajoute Constraint, Control, Obligation, Policy, Risk et Waiver DRAFT, sur le schéma SQL 6 existant. Les anciens profils restent figés.

Une politique est un objet métier versionné. Elle ne remplace pas la politique d’accès du serveur ni les mandats d’admission. Son applicabilité et ses contraintes sont calculées uniquement lorsqu’une expression AIR-Expr et des entrées explicites sont disponibles. Les textes restent à revoir et les résultats inconnus restent visibles.

Le service diagnostique utilise une baseline exacte, la lecture autorisée de toute sa fermeture, des contextes épinglés par contrainte et un budget commun. Les validités déclarées sont évaluées à une date fournie. Une dérogation déclarée n’a aucun effet sur le calcul tant que son autorité et son effectivité ne sont pas qualifiées par un mécanisme séparé ; ce mécanisme n’est pas ajouté ici.

Les trois dossiers Asteria doivent conserver leurs refus malgré une proposition de dérogation. La démonstration vérifie CLI, API, MCP et restauration. Les règles complètes de conformité, notamment AIR-V036 à AIR-V038, restent à réceptionner.
