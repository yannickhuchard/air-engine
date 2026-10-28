# Tranche 06 - expériences illustratives

POST /v1/experiments, simulate dans la CLI et air_simulate dans MCP exécutent des scénarios finis sur AIR-Expr. La requête fixe une baseline, une question, un modèle avec fonction exacte, description, limites et mesures, son digest SHA-256, puis les scénarios. Chaque scénario fixe un VerificationCase exact ciblant cette fonction, ses entrées typées et une valeur attendue pour chaque mesure.

Le moteur compare les observations calculées aux oracles fournis séparément. Cette séparation technique ne prouve pas leur indépendance : modèle et oracles restent à revoir. La classe de preuve est imposée à ILLUSTRATIVE. Aucun client ne peut se déclarer OBSERVED ou CALIBRATED. Les résultats ne qualifient pas automatiquement un VerificationCase et ne changent pas les portes de construction.

Les fonctions de calcul sont pures, sans shell, réseau, système métier ni chargement de code arbitraire. Limites : 32 scénarios, 16 mesures, 4 096 nœuds cumulés et 20 000 pas partagés. Erreur arithmétique et épuisement de budget produisent une comparaison UNKNOWN. Les entrées manquantes restent UNKNOWN, les contradictions CONFLICTING, et une observation différente de l'oracle VIOLATED. Un booléen false peut être le résultat attendu d'un refus ; sa conformité à l'oracle est distincte de sa valeur.

Les rapports fixent moteur, version d'AIR-Expr, baseline, digest du modèle, digest de demande, observations, oracles, coûts et limites. L'ordre des scénarios est normalisé. Le régime est DETERMINISTIC_RECALCULATION, une répétition, sans graine aléatoire. Le rejeu ne recalcule pas des entrées actuelles ni ne régénère de modèle IA.

scripts/demo_experiments.py exécute onze scénarios synthétiques : quatre SAV (nominal, doublon, autre client, persistance indisponible), quatre atelier (nominal, mesure ancienne, collecteur invalide, unité invalide), trois identités (nominal, dates contradictoires, compte non rapproché). Les dates contradictoires restent CONFLICTING ; le script réussit parce que ce refus de conclusion est attendu. Aucune commande de machine/IAM ni décision de garantie n'est produite.

scripts/demo_compute_http.py vérifie les mêmes calculs par CLI contre un serveur HTTP réel isolé. Le code de sortie de plan/simulate est 0 pour SATISFIED, 1 pour tout autre résultat de calcul ; les erreurs de commande conservent le traitement CLI existant. Les fichiers de requête contiennent tous les éléments nécessaires au rejeu sans conversation.

Ce sous-ensemble n'est ni un simulateur stochastique, ni une machine d'états complète, ni un plugin de code isolé, ni une calibration. Les types normatifs Experiment/SimulationRun/SimulationResult et jobs durables restent à compléter. Il constitue un premier moteur d'expériences calculées, avec limites de preuve explicites, pour L09.
