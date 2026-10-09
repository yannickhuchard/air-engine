# ADR-22 - Profil de construction et réception structurelle

Statut : IMPLEMENTED_SCOPED. Date : 19 septembre 2026.

Les neuf nouveaux types nécessitent des cibles de référence supplémentaires.
Nous introduisons air.construction/0.4 plutôt que de modifier l’ensemble de membres
admis dans une baseline foundation/0.2. Le profil participe au lockfile. Une
proposition conserve le profil de sa base. La migration d’un périmètre vers le
profil construction passe par une nouvelle baseline explicitement déclarée.

Les schémas et bindings documentaires retenus sont définis dans
[le contrat de tranche](../lot-construction.md). Les champs non implémentés du
catalogue sont refusés ou contraints à une liste vide, jamais assimilés à une
prise en charge complète. Les références persistées et leur fermeture sont typées.

La fermeture d’un graphe permet de conserver une conception incomplète. Une
évaluation séparée établit la traçabilité structurelle ; elle ne conclut pas à
la conformité métier ou à l’exécution de ses tests. Les cas de vérification
restent NOT_EXECUTED jusqu’à un futur service de résultats et de revue authentifiée.
Les autorités déclarées ne donnent aucun droit. La porte de réception demeure
bloquée pour cette raison, même quand les liens structurels sont complets.
