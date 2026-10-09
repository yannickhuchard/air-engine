# Synthèse de direction et pilotage de transformation

Chaque dossier AIR commence par un Management Summary, calculé depuis sa
baseline exacte et le résultat readiness de cette même version. Il expose
intention, objectifs, périmètre, décisions et conséquences, risques, inconnues,
hypothèses, jalons, consultations et enveloppe financière avec financement.
Chaque extrait conserve sa référence et son empreinte. Les sections affichent
au plus cinq éléments, classés par date puis identifiant, sans priorité inférée ;
les omissions sont comptées et les objets complets restent accessibles.

Le résumé est produit en HTML, Markdown et JSON avec les livrables. Une lecture
agentique ciblée utilise `air_compile_deliverables` avec
`only: ["00-management-summary"]`. Régénérer et appliquer le pack après chaque
baseline figée. Un ancien export reste attaché à son ancienne version ; il ne
synchronise pas automatiquement un navigateur ou une autre installation.

## De la transformation aux tâches de conception

| Objet | Contenu et liens |
| :--- | :--- |
| TransformationProgramme | Objectif, responsable, périmètre, dates, projets exacts et parent facultatif pour une hiérarchie de programmes |
| ArchitectureProject | Périmètre de conception, code, responsable, tâches exactes, dépendances de référence ou FINISH_TO_START et statut |
| ArchitectureTask | Projet exact, type de travail, responsable, livrables, preuves, prérequis et statut |
| SourcingStrategy | Choix RFI/RFP lié à une Decision, périmètre, jalon, critères, éléments concernés et preuves de consultation |

Les projets déclarent PLANNED, ACTIVE, ON_HOLD, COMPLETED ou CANCELLED. Les
tâches déclarent TODO, IN_PROGRESS, BLOCKED, DONE ou CANCELLED. Une tâche
terminale possède des preuves exactes et une date. Un projet terminal possède
une décision et une date de clôture et n'a aucune tâche active. Toutes les tâches
de sa révision exacte doivent être listées, sans tâche étrangère ou masquée.

Une tâche DONE exige des prérequis DONE : une annulation ne les accomplit pas.
Un projet ACTIVE ou COMPLETED exige ses prérequis FINISH_TO_START COMPLETED.
Les dépendances de référence n'imposent pas ce séquencement. Les cycles de
prérequis et de hiérarchie de programmes sont refusés. Un programme terminal
ne contient aucun projet ou sous-programme actif. Pour reprendre des travaux,
produire une nouvelle révision active et ses nouvelles références.

Les statuts sont des déclarations sourcées. Ils ne constituent pas une signature,
une réception indépendante ou une preuve de réalisation métier. La clôture de
conception, la porte readiness et la future implémentation restent distinctes.
Le statut global est calculé depuis programmes et projets aux pins sélectionnés ; un
mélange terminé/annulé reste CLOSED_MIXED. Les divergences exigent une revue.

## Graphe et requêtes avec un agent

Le site expose `transformation.html/json` au niveau global et par dossier,
avec un aperçu sur les accueils. Le graphe relie programmes, projets, tâches,
prérequis et consultations livrées. Chaque relation garde son objet témoin,
son sélecteur et l'empreinte de sa révision. Les cartes ouvrent une liste
descriptive avec responsables et sources, lisible au clavier sans JavaScript.
Au-delà de 90 objets, la vue graphique est explicitement bornée ; la liste et
le JSON restent complets dans les budgets de l'export.

Le même service déterministe dessert l'API, le CLI et le MCP :

```json
{
  "baselines": [
    {"id": "urn:exemple:baseline", "revision": 1, "digest": "sha256:REMPLACER"}
  ],
  "types": ["air.ArchitectureTask"],
  "statuses": ["TODO", "IN_PROGRESS", "BLOCKED"],
  "limit": 50
}
```

Remplacer l'exemple par les pins réels autorisés. Utiliser
`air_query_transformation`, `air transformation-query request.json` ou
`POST /v1/transformations/query`. Le filtre `owner` est facultatif. Suivre
`next_offset` pour les pages suivantes. Les totaux portent la portée complète
avant filtrage ; seules les relations entre objets de la page sont renvoyées,
avec le nombre d'arêtes omises. L'empreinte de projection identifie le graphe
complet ; l'empreinte du rapport identifie la réponse filtrée.

Pour un portefeuille, `air_index_portfolio` / `air portfolio-index` produisent
aussi le graphe global HTML/JSON depuis les baselines épinglées. Tous les pins
sont autorisés avant filtrage. Rien n'est écrit dans le registre par ces
lectures. Les versions divergentes restent distinctes, sans fusion silencieuse.
Le client doit rafraîchir son catalogue après mise à jour du MCP.

Ce pilotage vise une même instance locale AIR. Un architecte peut y gérer les
projets autorisés d'une entreprise ou d'un portefeuille. Les installations
autonomes de plusieurs entreprises ou clients ne sont pas fédérées. Leur
centralisation, synchronisation et partage automatique ne sont pas livrés.

## Consultation fournisseur dans les décisions d'architecture

Le choix RFI_THEN_RFP, RFP_DIRECT, RFI_ONLY ou NO_CONSULTATION fait partie des
décisions ADR/ADA. Sa Decision cite le périmètre exact dans `basis`. Le jalon
et les critères rendent la sélection examinable. La stratégie est visible
dans le sujet 25, le résumé et les graphes.

DRAFT et READY_TO_LAUNCH ne valent aucun envoi. LAUNCHED, EVALUATING et SELECTED
requièrent des sources exactes ; SELECTED désigne un Stakeholder fournisseur.
NO_CONSULTATION ne peut déclarer un lancement. Ces contrôles vérifient les
déclarations et leurs liens, sans envoyer un message ni certifier les documents.

## Application à ProxiBot

La contribution de conception (document historique ou livrable local non inclus)
est déposée par MCP authentifié, puis figée. Un programme contient le projet
ProxiBot actif : collecte documentaire et décisions sont déclarées terminées ;
calibration et revue indépendante restent bloquées. Camille Martin est fictive,
sans identité, habilitation ou avis réel créé.

La stratégie OEM est RFI_THEN_RFP en DRAFT, avec RFI préparé, critères et jalon
de sélection avant achat ou pilote. L'option vidéo incidente possède un contrôle
et une couverture de conception par les blocs edge, privacy et opérations.
Captation, assurance, permissions et matériel ne sont pas déclarés reçus.

Les cinq inconnues restent OPEN et deviennent INFORMATIONAL pour la réception
du design par accord utilisateur. Les obligations avant réalisation restent
explicites. La préparation courante (document historique ou livrable local non inclus)
et le résultat readiness exact font foi pour le score, sans valeur inventée.
