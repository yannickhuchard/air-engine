# Vues métier et ingénierie - tranche 19

Profil expérimental air.audience/0.19, reçu dans le périmètre décrit. Il ajoute Viewpoint DRAFT aux trente types de données précédents, soit 33 types persistables avec Baseline et ChangeSet. Le schéma SQL reste 6. L05/L06 demeurent partiels.

## Sélection explicite

Viewpoint référence des Stakeholder et leurs Concern. Le Selector déclare une liste de types et une liste de références exactes : la projection sélectionne leur union parmi les membres de la baseline. La fermeture contrôle ces références. Concern.addressed_by peut maintenant viser un Viewpoint ; les anciens profils fermés continuent à refuser ce nouveau type.

PresentationSpec fournit un titre et des sections ordonnées, chacune avec un identifiant, un intitulé et des types. Une section reste visible même vide. Un type ne peut appartenir qu’à une section ; les objets sélectionnés non classés apparaissent dans une section complémentaire. Les listes de types/références sont des ensembles canoniques, mais l’ordre des sections participe à l’empreinte. Voir [ADR 0036](adr/0036-viewpoint-selection-presentation.md).

## Compilation

~~~sh
python -m air audience-view request.json --output dossier-metier.html
~~~

request.json contient baseline et viewpoint, chacun avec id, revision et digest exacts. Le Viewpoint doit appartenir à la baseline. POST /v1/audience-views et l’outil MCP air_compile_audience_view appellent le même compilateur. Les options de credentials, --url et --ca-file sont les mêmes que pour les autres commandes. Le fichier de destination doit être nouveau.

La sortie affiche les valeurs et statuts déclarés, les objectifs, les préoccupations, les limites et les objets exclus de la sélection. Les objets restent consultables avec leurs métadonnées et leur provenance exactes. Aucun statut n’est recalculé. Une Decision documentée ne transforme pas un conflit en résolution vérifiée ; une Inference n’est pas exécutée par la vue.

source_mapping relie chaque fiche d’objet à sa révision, son empreinte et son ancre HTML. context_mapping relie les titres de contexte, parties prenantes, préoccupations et politique déclarée à leurs sources. Le contexte est borné à 1 MiB, la sortie à 4 MiB. Les octets peuvent ensuite être conservés par artifact-upload dans un dépôt séparé.

Les exports HTML de la CLI conservent maintenant exactement les octets UTF-8 générés, y compris sous Windows. Les scripts de démonstration utilisent aussi des fins de ligne explicites. Les archives précédentes restent immuables ; cette correction évite qu’une conversion LF vers CRLF modifie le fichier après calcul de son empreinte.

## Droits et limites

Toute la fermeture de lecture de la baseline est autorisée avant compilation. Une audience ne donne aucun droit supplémentaire. disclosure_policy est du texte déclaratif : ni masque de champs, ni anonymisation, ni déclassification. La sélection aide un utilisateur déjà habilité à lire un contexte ; elle ne prépare pas automatiquement une transmission à un tiers.

Le HTML ne contient ni script ni jeton. Les textes importés sont échappés et la CSP interdit les connexions actives. Le résultat est déterministe, hors ligne, sans Node ni navigateur imposé à l’installation.

Le type normatif View, Role, ToolchainSpec et la gestion de baselines référencées hors membres ne sont pas livrés par cette projection. Le catalogue distingue le Viewpoint persisté du contrat de service de compilation. Aucun profil AIR complet n’est revendiqué.

## Démonstration

Exécuter scripts/demo_artifacts.py si nécessaire après les démonstrations métier et connaissance, puis scripts/demo_audience.py. Une copie isolée des dossiers Astéria produit six HTML : métier et ingénierie pour SAV, atelier et IAM. Chaque baseline enrichie contient 52 objets, avec une partie prenante d’ingénierie distincte du responsable métier ; les anciennes restent identiques. La recette compare CLI/MCP, refuse l’accès SAV vers IAM et rejoue les vues après restauration. Rapport : tmp/demo-asteria/audience.json.

La recette navigateur facultative scripts/qualify_audience_browser.cjs vérifie les empreintes, mappings, clavier, affichage mobile, absence de débordement et violation effective de connect-src. Elle utilise un navigateur local explicitement désigné et Playwright ; ces outils restent réservés à la qualification.
