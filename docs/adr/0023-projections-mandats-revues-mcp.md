# ADR 0023 - projections et mandats explicites

Statut : adopté pour la tranche 05, 19 septembre 2026.

Le moteur conserve les sous-profils de types précédents. Diff, impact et vue sont des projections de baselines exactes ; elles n'accordent aucune autorité. L'impact expose les chemins de dépendance déclarés et ses limites de couverture.

Une politique locale versionnée accorde des actions par namespace à des sujets authentifiés. L'absence de politique conserve la simplicité de lecture/écriture locale ; les actions de revue et d'engagement nécessitent toujours un octroi explicite. Tous les adaptateurs partagent ces contrôles. L'accès transitif évite de révéler une dépendance partagée interdite dans un export autorisé en apparence.

Les revues sont des reçus de service immuables, séparés des brouillons normatifs. Ils fixent cible, baseline, preuves, auteur authentifié, politique et expiration. Une revue de son propre contenu est refusée. Ni l'authentification ni le reçu ne prouvent que l'acteur est humain ou que les scénarios métier ont été exécutés. La qualification ESTABLISHED reste fermée.

MCP expose les services existants en stdio et HTTP local sans dépendance supplémentaire. Le transport HTTP est stateless, sans SSE ni OAuth discovery ; l'exposition distante d'entreprise reste hors de cette tranche. Les annotations d'outils ne confèrent pas de permission.

Le schéma SQL 2 ajoute service_record, compatible avec les adaptateurs SQLite/PostgreSQL. La migration conserve les anciennes révisions. Une restauration SQLite dans une nouvelle instance révoque les anciens jetons et change la version de politique afin qu'un snapshot antérieur ne réactive pas implicitement une revue annulée depuis.

Conséquences : droits par objet/aspect et délégations, signatures, publication et engagements restent à compléter. Aucun lot entier ni profil normatif complet n'est déclaré reçu à partir de ces seuls services.
