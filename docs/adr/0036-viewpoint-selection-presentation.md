# ADR 0036 - Viewpoint et compilation déterministe par audience

Statut : accepté pour le binding air.audience/0.19, vérifié par les tests et les trois dossiers. Référence : white paper 14 et A.12, pages 28 et 52. L05/L06 restent partiels.

Les vues existantes exposent une baseline entière. Viewpoint introduit une audience Stakeholder, des Concern, un Selector et une PresentationSpec explicites. Les records Selector et PresentationSpec ne sont pas détaillés par le white paper ; le présent binding fournit un sous-ensemble fini, sans exécution de texte importé.

Selector contient binding=air.selector/0.19, types et objects. La sélection est l’union des membres dont le type est désigné et des références exactes désignées ; au moins un des deux ensembles doit être non vide. Aucun parcours implicite, SQL ou DSL externe n’est évalué. Les références exactes doivent fermer dans la baseline. Les types et références sont des ensembles canoniques.

PresentationSpec contient format=air.audience-html/0.19, title et sections ordonnées. Chaque section possède un identifiant, un intitulé et un ensemble de types. Les identifiants sont uniques ; un type ne figure que dans une section. air-unassigned est réservé à la section générée pour les objets sélectionnés dont le type n’est pas classé. L’ordre des sections est significatif et participe à l’empreinte.

L’audience est bornée à 64 Stakeholder et les préoccupations à 256 Concern. Chaque préoccupation doit être déclarée par au moins un membre de l’audience. Le champ Concern.addressed_by peut désormais viser Viewpoint ; la fermeture des anciens profils continue à refuser ce type absent de leurs ensembles. Les anciennes révisions et leurs empreintes ne changent pas. Role demeure hors de ce premier incrément.

Le service reçoit une baseline exacte et un Viewpoint exact appartenant à celle-ci. Toute la fermeture de lecture de la baseline est autorisée avant la sélection. L’audience n’est pas une liste d’ACL ; disclosure_policy reste un texte déclaratif, jamais un programme de droits. La projection est destinée à un utilisateur déjà autorisé sur ce contexte. Les champs ne sont pas masqués et la sélection ne vaut ni anonymisation, ni déclassification, ni export autorisé vers un tiers.

Les objets sélectionnés sont rendus avec leurs valeurs, états, références et provenance exacts. Les sorties indiquent le nombre d’objets exclus et qu’ils ne sont pas évalués par la vue. Les sections vides restent visibles. Aucune narration générée ou recalcul métier ne change le sens d’une valeur. Les mappings identifient chaque objet, révision, empreinte et ancre HTML. Le contexte est borné à 1 MiB, la sortie à 4 MiB.

Le rendu ne contient aucun script, jeton ou connexion distante. Les textes et objets sont échappés en HTML ; une CSP borne le style intégré. CLI, API et MCP appellent le même service pur. Les octets peuvent ensuite être conservés par le service d’artefacts, sous un dépôt distinct et authentifié.

Le type normatif View n’est pas compté comme persistable à ce stade. Son contrat requiert des références à des baselines hors membres, ToolchainSpec, output et source_mapping ; son ajout fera l’objet d’une extension explicite. Ce compilateur ne suffit pas à revendiquer la réception complète des vues du white paper.
