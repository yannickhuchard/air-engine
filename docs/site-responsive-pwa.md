# Atlas responsive et PWA des dossiers AIR

Développement **0.35.0.dev1**. La distribution publique rc9 et le plugin soumis
restent distincts. Le site est une lecture des designs exportés ; il n’édite pas
le registre et n’exécute pas les solutions métier.

## Présentation

L’atlas utilise une surface de lecture blanche, un rail de navigation bleu-gris
et un en-tête pétrole. Palette : texte `#17333c`, en-tête `#153f4a`, fond
`#f1f6f7`, liens `#17687c`, repère `#6ed5c2`. Les couleurs de l’ontologie
conservent leurs significations : composants, données, fonctions et décisions.
Bahnschrift, lorsqu’elle est disponible sur le poste, distingue les titres ;
Segoe UI/Tahoma portent la lecture. Aucun téléchargement de police.

```text
Ordinateur                         Téléphone
AIR | projet | accès hors ligne    AIR | accès hors ligne
Navigation | sujet de focus        Projet
           | diagrammes, sources   Explorer les dossiers [replié]
                                  Sujet, diagrammes, sources
```

La structure privilégie le dossier et le sujet, avec alignement à gauche,
paragraphes courts et décisions/limites visibles. Les états de conception
restent séparés ; les cartes de dossier indiquent leur révision et leur porte.
Les familles de sujets sont repliables, le groupe du sujet courant est ouvert.
Sous 900 px, le menu global est replié et le contenu reste immédiatement lisible.
Sans JavaScript, toute la navigation reste accessible via les éléments `details`.
Les tableaux et diagrammes défilent dans leur propre surface. Focus clavier,
lien d’évitement, commandes tactiles et préférence de mouvement réduit sont
conservés. La PWA se configure dans « Accès hors ligne ».

## Lecture directe et installation

L’ouverture de `livrables/site/index.html` fonctionne directement sur disque,
sans serveur, cloud ou Node. Ce mode ne crée pas de service worker ni de cache
persistant dans le navigateur. Pour l’installation PWA et sa copie hors ligne :

```powershell
.venv/Scripts/python.exe -m air.site_server D:/architecture/projet/livrables/site --port 8741
```

Ouvrir l’adresse affichée `http://127.0.0.1:8741/index.html`, puis choisir
« Conserver hors ligne ». Le navigateur peut proposer l’installation, ou la
commande « Installer l’application » lorsqu’il expose cette possibilité.
Le port choisi doit être conservé pour retrouver cette installation et ses données.
Arrêter le serveur avec Ctrl+C. Aucun accès au serveur AIR, à sa base ou à ses
identités n’est requis pour lire cet export déjà autorisé.

L’installation PWA requiert HTTPS ou une adresse de boucle locale, selon les
[critères des navigateurs](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).
Le module Python écoute uniquement sur `127.0.0.1`, sert la liste exacte du
manifeste et refuse listes de répertoires, fichiers non déclarés, symlinks,
chemins traversants, hôtes inattendus et écritures. Il vérifie les empreintes à
chaque lecture. Le service worker utilise une CSP limitée à la même origine.
Le serveur local n’est pas un hébergement partagé ou un dispositif de contrôle
d’accès pour une diffusion entreprise : ce profil reste celui du poste autonome.

## Copie hors ligne et mises à jour

La conservation est explicite : elle copie les données de tous les dossiers
exportés dans le stockage du navigateur. Ne conserver le site que sur un poste
autorisé à posséder ces données. Elle inclut sujets, diagrammes, sources,
documents Markdown, graphes, calendrier et modèle exact du site. La copie JSON
du modèle dans le site est compacte ; elle représente les mêmes données et
conserve les empreintes/artefacts, comme l’export principal du pack.

Le manifeste PWA expose une identité stable pour ce chemin, les icônes SVG AIR
192/512 px et un lancement autonome. Le service worker vérifie SHA-256 de chaque
ressource avant d’activer une génération. Une copie interrompue/incohérente est
supprimée sans remplacer la génération complète précédente. Les requêtes
extérieures et les fichiers non déclarés ne sont pas mis en cache. Aucun effet
sur les permissions, portes ou validations du design.

Après régénération, redémarrer le serveur : ses empreintes sont épinglées au
démarrage. La nouvelle copie complète attend « Appliquer la nouvelle version »
si une ancienne version est ouverte. Cette action actualise la page ; les autres
pages ouvertes signalent qu’une recharge est nécessaire. Les caches sont séparés
par origine, chemin et empreinte de génération. Une version active sert uniquement
ses ressources vérifiées, sans mélanger un nouveau HTML avec d’anciens scripts.

« Effacer la copie hors ligne » supprime les caches de ce chemin et désinscrit
son worker, sans toucher les autres chemins ou les fichiers sur disque. Fermer
les pages encore ouvertes termine leur utilisation de l’ancien worker.
Le navigateur peut évincer son stockage : conserver l’export original pour
restaurer la copie. Le site n’est pas un système de sauvegarde ou de synchronisation.

## Qualification et limites

Les tests du serveur, du pack et du navigateur sont locaux, sans CI. La recette
PWA couvre manifeste/icônes, opt-in, lecture hors ligne, changement complet de
génération, échec d’une nouvelle copie, effacement ciblé et conservation d’un
cache appartenant à un autre chemin. L’installation effective via l’interface
du système d’exploitation n’est pas exercée par le navigateur headless ; les
autres navigateurs et appareils ne sont pas qualifiés par cette recette.
Le test navigateur nécessite facultativement Node/Playwright, qui ne sont pas
des dépendances d’installation ou de fonctionnement d’AIR.

Le pack conserve ses plafonds de taille ; fractionner une compilation trop
grande en packs de baselines exactes. Une copie locale complète ne prouve pas
la conformité totale AIR, la complétude métier, une migration réalisée ou une
nouvelle qualification des clients agentiques.
