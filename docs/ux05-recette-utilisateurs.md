# UX05 : protocole de réception formative

État du 4 octobre 2026 : préparé, aucune séance exécutée et aucun résultat
participant reçu. Les tests automatisés UX01 à UX04 ne mesurent ni compréhension
humaine, ni satisfaction, ni temps de travail réel. Ils ne remplacent pas ces séances.

La [fiche de séance](ux05-fiche-seance.md) est prête à copier dans `reviews/`.
L’audit propose deux vagues et 16 participants ; les six publics ci-dessous
organisent les séances, sans réduire cette cible à six validations automatiques.

Utiliser les trois dossiers fictifs Asteria, dans leur site courant. Prévoir
une séance de 25 à 35 minutes par public : COMEX, métier, DSI, architecture
entreprise, architecture solution et réalisation. Un participant peut couvrir
plusieurs responsabilités, à consigner. Ne pas enregistrer de données personnelles
ou de dossier client réel dans les preuves publiées.

Le modérateur donne une tâche et observe sans indiquer le chemin attendu.
Demander au participant de verbaliser ce qu’il comprend. Consigner réussite
autonome, aide nécessaire, erreur de compréhension et élément qui l’a produite.
Mesurer le temps observé ; ne pas lui substituer un temps de script navigateur.

| Tâche | Question de réception | Trace à conserver |
| --- | --- | --- |
| Choisir un dossier et son public | Comprend-il l’intention et distingue-t-il les trois dossiers ? | Dossier, public, chemin choisi et reformulation |
| Suivre un mécanisme | Peut-il retrouver une fonction, son contrat et un composant, puis expliquer le sens des liens ? | Sources exactes et confusion éventuelle entre association et appel |
| Examiner une décision ou un manque | Distingue-t-il déclaration, absence, contrôle calculé et preuve encore à produire ? | Question choisie, source et prochaine action proposée |
| Préparer la réalisation | Peut-il retrouver contrats, responsabilités et critères sans attribuer un propriétaire comme responsable opérationnel ? | Fiche choisie, absence repérée et clarification demandée |
| Transmettre une question | Comprend-il ce qui part dans la capsule et peut-il vérifier son contexte dans son client ? | Capsule, reçu expurgé et surface cliente exacte |
| Reprendre ou diagnostiquer un écart | Identifie-t-il une autre baseline, identité, politique ou catalogue et sait-il arrêter une écriture inappropriée ? | Diagnostic réel et action de résolution |
| Lire sur mobile et hors ligne | Trouve-t-il la même information, les sources et les actions au clavier ou sur écran tactile ? | Écran, mode réseau et obstacle observé |

Pour le COMEX, privilégier intention, valeur, risques et arbitrages. Pour le
métier, résultat attendu et changement de travail. Pour la DSI, exigences de
qualité, engagements et exploitation. Pour l’architecture entreprise, capacités,
principes et trajectoire. Pour l’architecture solution, mécanismes et données.
Pour la réalisation, interfaces, dépendances, RACI, critères et vérifications.

Une capsule dans un assistant natif requiert un connecteur réellement connecté
et un catalogue observé. Identifier la surface exacte : ChatGPT conversationnel,
Codex, Claude Code ou un autre IDE. Ne pas qualifier un client par la réussite
du TestClient API, d’un navigateur isolé ou d’une autre surface. Conserver les
refus URN et les outils absents ; les séances peuvent documenter ces obstacles
sans les transformer en résultat favorable. UX00 reste une réception distincte.

## Décider à partir des observations

Un obstacle qui mène au mauvais dossier, à une divulgation, à un dépôt indu
ou à une lecture erronée d’une preuve bloque la réception de ce parcours.
Une difficulté d’accès, de lisibilité ou de compréhension répétée justifie une
correction prioritaire et un nouveau parcours après cette correction. Un avis
esthétique isolé est consigné avec son contexte, sans remplacer les tâches.

Pour chaque séance, conserver : identifiant anonyme, responsabilités, dossier
et baseline exacte, version du site, surface cliente, écran/mode de lecture,
tâches observées, aides données, erreurs, citations expurgées, décisions de
correction et contrôles non exécutés. Ranger les notes privées dans `reviews/`
du dossier de travail ; publier uniquement un reçu expurgé de la réception.

Le statut demeure `NOT_EXECUTED` jusqu’aux premières séances. Une séance reçue
ne vaut pas certification WCAG, validation métier des neuf tests Asteria ou
qualification générale de production. Le périmètre publié doit citer les publics,
surfaces, versions et tâches effectivement observés.
