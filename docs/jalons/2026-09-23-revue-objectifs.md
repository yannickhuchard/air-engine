# Jalon du 23 septembre 2026 - revue au regard de l’objectif

Point d’étape de la construction d’AIR, après la tranche 31 et l’essai réel de ChatGPT avec AIR par tunnel MCP.
L’objectif visé : une fondation universelle, pilotée par des agents, pour concevoir et planifier en totalité une
architecture **prête à construire**, utilisable par une société de développement ou une usine logicielle
automatisée, et opposable comme **document contractuel** pour conclure une affaire, avec une **preuve par simulation
vérifiée**.

## Verdict

AIR utilisé par un agent est déjà une fondation crédible pour la moitié « conception ». Il ne l’est pas encore pour
l’autre moitié : un dossier prêt à construire, contractuellement utilisable et prouvé par simulation vérifiée. Le
dossier assurance santé ne tiendrait pas aujourd’hui comme annexe de contrat : rien n’y est vérifié, relu ni signé,
et les simulations d’AIR sont illustratives par construction.

## Le dossier au regard de l’objectif

| Critère | État | Preuve dans AIR |
| --- | --- | --- |
| Conception exacte, tracée, immuable | Solide | 248 objets plateforme et 110 fraude figés par empreinte ; chaque exigence tracée à sa source ; exclusions écrites |
| Solidité structurelle MECE et DDD | Solide, structure seulement | Aucune violation dans les deux projets |
| Prêt à construire | Pas encore | Porte de construction bloquée : 41 diagnostics plateforme, 55 fraude ; aucune unité de construction côté fraude ni pour la passerelle MCP ; interface de paiement manquante |
| Vérifié | Non | 29 cas de vérification, aucun exécuté ; 8 révisions figées sans revue ; rien d’approuvé |
| Planification | Faible | Estimations par règle non calibrée (8 jours par opération) ; aucun jalon, plan de livraison ni plan de ressources |
| Usage contractuel | Pas encore | Tout est brouillon ; publication signée non implémentée ; rien d’approuvé |
| Preuve par simulation vérifiée | Absente | Rejeu et simulation illustratifs ; simulation calibrée non implémentée ; un cycle de vie à la fois ; conditions de workflow en texte ; cibles de latence non simulables |
| Couverture d’une architecture totale | Partielle | 60 types couvrent métier, exigences, données, contrats, cycles de vie, gouvernance et construction ; manquent déploiement, infrastructure, zones de confiance, interfaces, migration, coûts, AsyncAPI, carte de contextes |

Décisions de conception relevées par les agents : date de refus jamais enregistrée ; clôture qui éteint le droit de
réouverture ; réouvertures illimitées ; annulation possible après paiement ; événement de réouverture sans
identifiant d’adhérent ; aucun rôle sur les 29 opérations ; 8 événements sans canal ; quatre cycles de vie non
modélisés (contrat, devis, adhésion, attribution de rôle).

## ChatGPT avec AIR au regard de l’objectif

Ce qui fonctionne : usage natif par tunnel, 15 appels sans échec, guide suivi sans consigne, faits rapportés
fidèlement, validation à blanc utilisée avec intelligence, « ne rien déposer » respecté ; même fondation pour Claude
Code, Codex et ChatGPT.

Ce qui fait obstacle pour une usine logicielle ou un contrat : la production de l’agent n’est pas une preuve (ses
estimations et choix sont un jugement de modèle, et AIR ne dit pas quel agent, modèle ou conversation a produit un
brouillon) ; l’agent n’est pas reproductible ; ChatGPT voit des outils d’engagement que le serveur refuse ; l’application
tourne en mode développeur derrière un script et une clé ; l’historique de conversation reste dans ChatGPT.

## Ce qu’il faudrait

1. **Une porte « prêt à construire » définie** : chaîne de construction fermée, décisions tranchées, critères de
   passage explicites pour que « prêt » soit un résultat.
2. **Une preuve par simulation digne de confiance** : conditions de workflow en AIR-Expr, simulation de bout en bout
   entre services avec modèle de performance par étape, calibration sur des mesures, chaque exécution enregistrée comme
   preuve liée à son cas de vérification et confirmée par une revue humaine indépendante.
3. **Une annexe de contrat** : publication signée, vue « cahier des charges » générée depuis le dossier, estimations
   avec intervalles de confiance, ChangeSets comme clause de gestion des changements ; l’adéquation juridique relève du
   conseil.
4. **Un passage de relais à l’usine logicielle** : paquet de construction par unité (API, AsyncAPI, schémas, tests
   d’acceptation, découpage du travail) et boucle de conformité à l’exécution.
5. **Une gouvernance des agents** : agent, modèle et session enregistrés sur chaque brouillon ; outils exposés selon
   l’accès ; schémas de sortie ; qualification des vrais clients.

Suite décidée le même jour : points 1 et 2, et un dossier de livrables pour l’équipe de réalisation, dérivé du graphe.
