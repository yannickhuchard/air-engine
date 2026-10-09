# Workbench portable - tranche 14

Version 0.14.0.dev1 ; 247 tests réussis sur SQLite et PostgreSQL 18.6. Recettes navigateur, dépôt des contributions et M1 réussies. L08.1, L08.3 et L08.4.

Le premier Workbench est un fichier HTML autonome généré à partir d’une baseline exacte, après contrôle de toutes les dépendances par les mêmes règles d’accès que l’API. Il fonctionne hors ligne, sans Node, CDN, service IA ou secret embarqué. Le fichier est un export de données : ses destinataires doivent rester autorisés à les consulter.

La vue offre recherche, filtre par type, navigation dans les références entrantes et sortantes, lecture des propriétés et des preuves. Elle conserve la baseline, les révisions et les limites de qualification. Les textes du modèle seront insérés comme texte, jamais exécutés comme HTML ou JavaScript.

Un formulaire prépare une Contribution DRAFT ciblant l’objet sélectionné. Son téléchargement produit une requête JSON pour collaboration-submit ; il ne modifie pas le registre. L’identité provient du contexte authentifié de génération et devra être revérifiée à la soumission. Aucun jeton ne sera inclus dans le HTML ou le JSON préparé.

La CLI, l’API et MCP appellent le même générateur. La recette vérifiera les filtrages, références, chaîne observation-décision, préparation d’une contribution, refus d’accès, contenus hostiles, absence d’accès réseau et usage clavier sur les trois dossiers. Les interfaces de revue habilitée, admission, édition graphique et synchronisation serveur demeurent des extensions distinctes.

## Commandes

Créer un fichier de requête contenant baseline avec id, revision et digest exacts, puis utiliser :

~~~sh
python -m air workbench requete.json --output dossier.html --credential agent.json
~~~

Le fichier de sortie doit être nouveau. L’API est POST /v1/workbench ; l’outil MCP est air_compile_workbench. Les trois bindings utilisent le même générateur. Ouvrir dossier.html dans le navigateur, choisir un objet et préparer une contribution si le contexte autorisé permet son écriture. Déposer le JSON téléchargé avec collaboration-submit ; le serveur recontrôle toutes les conditions.

## Recette

scripts/demo_workbench.py génère les trois dossiers par HTTP, compare CLI/MCP et restaure leurs baselines. scripts/workbench_hostile_fixture.py ajoute un modèle de texte hostile en lecture seule. La recette facultative scripts/qualify_workbench_browser.cjs utilise Node, Playwright et un navigateur Chromium installé ; elle vérifie recherche, filtres, liens, clavier, écran étroit, téléchargement, CSP et rendu sans JavaScript. scripts/verify_workbench_contributions.py dépose les trois contributions ainsi téléchargées dans leur instance fictive, puis restaure leurs reçus.

Les HTML et captures sont dans tmp/demo-asteria/workbench. Les données embarquées sont fictives ; un export de données réelles doit respecter leurs droits de diffusion.
