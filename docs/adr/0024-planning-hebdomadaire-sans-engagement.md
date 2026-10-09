# ADR 0024 - premier calcul capacitaire sans engagement

Statut : adopté pour la tranche 06, 19 septembre 2026.

Implémenter un service de scénario borné avant d'introduire les engagements. Les demandes visent des ConstructionUnit de baselines exactes et les données capacitaires portent Scope, Source et dates. Les entrées déclarées ne sont pas transformées en engagements authentifiés.

Choisir des périodes de sept jours et des décimaux exacts ; conserver offre brute, obligations et réservations distinctes. Refuser le double comptage d'une même identité entre pools, les cycles de précédence et les unités incohérentes. Les sources inconnues ou périmées bloquent une conclusion favorable.

La stratégie initiale est une heuristique sérielle déterministe, avec priorités fournies par l'appelant et déplacement vers le futur. Pas d'optimalité affirmée, pas d'infaisabilité globale déduite de l'échec de l'heuristique. Les plans comparés ne modifient pas le registre.

Conséquences : le protocole de calcul ne revendique pas les types normatifs complets du white paper. Les futurs services d'admission devront vérifier leurs propres entrées d'autorité et ne pourront accepter un rapport de scénario comme une preuve d'engagement.
