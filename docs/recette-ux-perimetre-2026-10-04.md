# Réception UX : périmètre vérifié au 4 octobre 2026

Les fonctions locales UX01 à UX04 sont livrées. Cette réception complémentaire
vérifie la coopération sur les transports réels et précise les deux réceptions
encore ouvertes. Elle ne clôture ni UX00 natif, ni UX05 avec des participants.
Voir le reçu expurgé (document historique ou livrable local non inclus).

## Trois dossiers, deux transports réels

SAV, atelier et identités Asteria fournissent chacun 37 capsules. Pour les 111
capsules, HTTP MCP sur une API locale réelle et le processus MCP stdio renvoient
le même résultat de contexte. Les 111 reprises dans de nouveaux processus stdio
réussissent aussi ; leurs résultats correspondent aux reprises HTTP. Cela
représente 444 appels de capsule vérifiés, sans assistant conversationnel.

Les trois identités de lecture sont limitées à leur namespace et aux références
partagées. Chaque transport refuse six lectures entre namespaces, trois reçus
dont l’identité a été modifiée et trois capsules modifiées. Une requête HTTP sans
authentification est refusée. Les codes et statuts des refus correspondent ;
leur prose peut différer, car l’API omet le message d’exception des refus d’accès.
Les identifiants de test sont révoqués et le serveur de test est arrêté.
Aucune révision d’architecture n’est écrite par cette recette.

Le catalogue observé contient 57 outils en mode automatique de lecture. Ses
schémas correspondent aux outils courants. Par rapport au profil fixe `read`,
les deux outils supplémentaires sont les calculs privés `air_submit_job` et
`air_cancel_job`. Cette différence autorisée est conservée dans le reçu.

Les 12 parcours navigateur sur quatre largeurs sont reçus, ainsi que les trois
dossiers sans JavaScript. La copie réelle dans Edge isolé préserve la demande,
après normalisation des fins de ligne Windows ; le JSON et son empreinte restent
exacts. Un refus simulé du presse-papiers permet la copie manuelle avec sélection
visible. Ces contrôles ne sont pas des séances avec des utilisateurs.
19 tests locaux pertinents passent. Le pack et les trois baselines restent
identiques à la réception UX04, avec leurs gates `NOT_READY` et leurs neuf tests
métier non exécutés. Aucune CI n’a été lancée.

Reproduction, avec Python seul pour le protocole :

```powershell
.venv/Scripts/python.exe scripts/demo_architecture_site.py --output tmp/recette-ux-neuve
.venv/Scripts/python.exe scripts/qualify_question_transports.py tmp/recette-ux-neuve/site-demo.json
```

Choisir un nouveau répertoire à chaque réception. Le script refuse un home
déjà configuré, une politique existante et `AIR_DATABASE_URL`. Il ne configure
que le registre SQLite fictif créé par cette démonstration, sous `tmp/`.
La recette navigateur optionnelle utilise Edge et Playwright ; ils ne sont
pas des dépendances obligatoires d’installation AIR.

## UX00 : le service courant et le client chargé diffèrent

Le service API du banc synthétique connecté a été sauvegardé et redémarré sur
le code courant. L’identité et l’empreinte de sa baseline restent inchangées.
Ses capacités annoncent les 86 outils supportés, dont `air_resume_question`.
Une lecture API authentifiée de l’URN exacte réussit.

La même URN reste rejetée **avant AIR** par le connecteur exposé dans Codex,
sur une contrainte `format: uri`. `air_resume_question` et le branding ne sont
pas exposés dans son catalogue chargé. Un ancien résultat `tools/list` du tunnel
confirme un schéma URI et des outils anciens ; il ne constitue pas une nouvelle
découverte du client. Le catalogue complet avec ses schémas actuellement chargés
dans le client n’est pas accessible ici. La cause précise du rejet doit encore
être confirmée après une découverte fraîche.

Le navigateur pilotable expose le navigateur intégré à Codex, sans application
native accessible. Sa session web ChatGPT est non authentifiée. Le rafraîchissement
du connecteur dans une session ChatGPT connectée n’a donc pas pu être réalisé. Aucune
réception native ChatGPT des nouveautés n’est annoncée.

Pour clôturer UX00 :

1. Relancer l’adaptateur stdio du tunnel existant et recharger la découverte
   dans le client authentifié. Le redémarrage de l’API ne recharge pas les
   modules Python d’un processus stdio déjà en mémoire. Conserver ses droits,
   son identité et son fichier protégé d’identifiants.
2. Capturer le véritable `tools/list` et vérifier schémas, profil et actions
   avec le [contrat client](contrat-client-agent.md). Ne pas remplacer cette
   observation par le catalogue du serveur.
3. Relire trois références exactes du registre connecté, puis reprendre une
   capsule de ce même registre. Vérifier baseline, sources et identité dans
   une nouvelle conversation. Arrêter en cas d’écart ; ne pas remplacer une URN
   par une URL inventée ni envoyer une capsule Asteria dans le mauvais registre.

## UX05 : le kit est prêt, les observations restent à recueillir

Le [protocole](ux05-recette-utilisateurs.md) et la
[fiche de séance](ux05-fiche-seance.md) couvrent les six publics. Les deux vagues
et 16 participants proposés dans l’audit restent une cible. Aucune personne
n’a encore effectué une séance dans cette réception. UX05 demeure
`NOT_EXECUTED` jusqu’aux observations réelles, aux corrections prioritaires
et aux nouveaux parcours après correction.

Les preuves historiques rc9/G1 et la distribution publique restent distinctes
de cette branche de développement `0.35.0.dev1`. Cette réception technique
ne vaut ni qualification générale de production, ni certification WCAG,
ni validation métier de la solution Asteria conçue pour une réalisation ultérieure.
