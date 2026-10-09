# ADR 41 - Replay borné des machines à états

Décision du 20 septembre 2026 : ajouter le binding expérimental air.state/0.24, sans migration SQL. StateMachine reste DRAFT et les anciens profils restent figés.

La simulation reçoit uniquement des contextes typés explicites, une baseline et une machine exactes. Les invariants sont contrôlés avant et après les transitions ; une cible n’est appliquée qu’après ces contrôles. Des gardes ambiguës ne sont pas départagées. Les contextes successifs sont indépendants et air_state est fourni par le moteur. Une valeur inconnue n’est pas remplacée par une supposition.

Les budgets d’évaluation sont partagés par tout le replay. Le résultat distingue transitions appliquées, boucles sans changement d’état, propositions refusées et arrêt sur limite. Les effets déclarés ne sont jamais exécutés. Les droits couvrent toute la baseline.

Ce service pur est accessible par CLI, API et MCP. Il constitue une expérience illustrative reproductible et ne qualifie ni un système externe, ni la fidélité d’un simulateur, ni une autorisation métier. Le contrat complet figure dans docs/lot-machines-etats.md ; la qualification est conservée dans docs/traceability/verification-state-replay.json.
