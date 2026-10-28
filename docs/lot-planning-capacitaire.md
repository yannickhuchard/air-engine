# Tranche 06 - planning capacitaire hebdomadaire

Le service air.weekly-planning/0.6 réalise un premier calcul des §§10–11 et de l'arithmétique F.7 du white paper. Ce n'est pas encore l'implémentation complète des types ConstructionPlan, ResourcePool, CapacitySupply ou AdmissionRequest. Le contrat de calcul est distinct du modèle normatif persistable.

POST /v1/plans, la commande plan et l'outil MCP air_plan partagent le moteur et les contrôles de lecture. Le résultat ne crée aucune réservation, aucun reçu d'admission, aucun événement d'engagement. Les quantités sont des entrées de scénario déclarées, reliées à une Source exacte ; leur présence dans une requête authentifiée ne vaut pas confirmation du responsable de ressources.

## Entrées et calcul

Le schéma strict est dans src/air/planning.py (REQUEST), découvert également par tools/list MCP. La requête contient basis=SCENARIO_INPUT, as_of UTC, unit=FTE, periods, pools, demands, dependencies, priority_order et strategy. Les périodes contiguës sont des intervalles semi-ouverts de sept jours, au maximum 104. Les valeurs décimales sont des chaînes exactes, sans flottant. Aucun multiplicateur d'agents ni conversion implicite d'effort en durée.

Chaque pool fixe un Scope et une Source par id/révision/digest, des identités de ressources uniques, l'état de disponibilité, date d'observation et expiration, puis trois vecteurs distincts : gross, baseline_obligations et existing_reservations. Le moteur calcule gross - obligations - réservations. Une observation inconnue vaut null. Les mêmes ressources dans deux pools sont refusées : le sous-profil exige des agrégats disjoints, sans prétendre résoudre l'affectation multi-compétences.

Chaque demande fixe sa baseline fermée, une ConstructionUnit exacte, son pool et le vecteur per_week. Une seule révision par unité, une demande par couple unité/pool. Les dépendances strictes forment un DAG ; les références absentes et les cycles sont refusés. priority_order contient toutes les unités et fixe le départage déterministe.

AS_PROPOSED mesure les écarts par pool/période et la précédence. Une source indisponible, expirée à as_of ou incomplète produit UNKNOWN pour les cellules concernées ; une violation connue reste visible. La somme totale des déficits vaut null lorsque sa couverture est incomplète ; une somme des déficits connus est exposée séparément.

SERIAL_EARLIEST_FEASIBLE suit l'ordre topologique et les priorités, puis cherche la première position compatible en décalant chaque profil de demande entier vers le futur. Il ne réduit pas les durées et ne coupe pas implicitement les tâches. Le candidat n'est retourné que lorsque toutes les unités sont placées. Échec de recherche ou épuisement de budget ne prouve pas une impossibilité globale : statut UNKNOWN, diagnostic explicite, aucun faux optimum. Budget : 10 000 positions candidates ; la borne et l'écart d'optimalité restent absents.

## Résultats vérifiés

Le parcours scripts/demo_planning.py calcule les trois demandes Asteria. Offre brute 6 ETP, obligations courantes 2, réservations existantes 0 : offre disponible 4. La proposition initiale demande 5 ETP sur les quatre premières semaines, déficit 4 ETP-semaines. Avec la priorité SAV, identités, atelier, la variante retarde l'atelier aux semaines 5–8 et donne 3 puis 2 ETP. Elle est faisable pour ces contraintes seulement.

Les tests F.7 séparent ingénieurs et analystes : déficits initiaux 8 et 4 ; deux ingénieurs disponibles dès la troisième semaine laissent 4 et 4. L'offre après un jalon ne couvre pas le manque antérieur. Sont aussi testés réservations existantes, doublons de ressources, sources expirées/injoignables, dépendances cycliques, limites de calendriers, digests faux, contexte décimal et confidentialité inter-dossiers.

## Limites et suite

Ce moteur ne modélise pas encore jours fériés, money/budgets, substitutions qualifiées, apprentissage, travail en cours protégé, mobilisation, engagements autoritatifs ou solveur global. Les dates as_of font partie du contexte figé : rejouer le contexte historique est reproductible ; obtenir une offre actuelle nécessite une nouvelle requête sourcée.

DEMO-PORTEFEUILLE-2 reste ouvert : simulation, admission concurrente, perte de condition avant activation et restauration des engagements ne sont pas implémentées par ce seul calcul. Les tests arithmétiques ne permettent pas de déclarer ces garanties reçues.
