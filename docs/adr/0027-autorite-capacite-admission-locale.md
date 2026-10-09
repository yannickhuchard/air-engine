# ADR 0027 - Autorité et réservations dans le registre central

Statut : accepté pour air.local-resource-admission/0.10 ; portée locale expérimentale.

La capacité de scénario ne peut devenir un engagement par un champ approuvé dans une requête. Les offres proviennent de sujets authentifiés ayant un mandat capacity, fixent des ressources distinctes et une source exacte, et sont versionnées avec comparaison du dernier reçu.

La politique métier est engagée en SQL avec génération monotone. Les décisions prennent le verrou du registre, vérifient identités et politique, relisent les réservations, puis inscrivent reçu et engagements dans la même transaction. PostgreSQL utilise le verrou de ligne ; SQLite BEGIN IMMEDIATE. Le calcul pur conserve son service et ses limites. L’admission utilise son résultat et fige la variante approuvée, sans réordonnancement silencieux après revue.

Les ETP sont stockés en micro-ETP entiers et les fenêtres en secondes UTC, ce qui évite les arrondis binaires et permet les mêmes invariants dans les deux moteurs. Les projections de lecture sont cohérentes dans une transaction de lecture ; les révisions et reçus restent immuables.

L’activation recontrôle les conditions et protège le travail déjà engagé. Un changement d’offre ou d’autorité ne libère aucune réservation. Une répétition renvoie le reçu historique avec created=false et ne constitue pas une nouvelle autorisation. Les renouvellements et clôtures explicites sont à développer dans la tranche suivante.

Conséquences : transactions sérialisées au niveau du registre initial, pas de coordination distribuée, pas d’action externe, pas de qualification de réception métier. Les tests concurrents et le parcours Asteria vérifient le périmètre livré, sans revendiquer la conformité aux 143 types du white paper.
