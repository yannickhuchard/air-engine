# UX02 : design du Projet d’architecture et lecture du graphe

## Direction retenue avant implémentation

Le site sert à comprendre une transformation, examiner ses choix et préparer
une réalisation. La carte d’architecture est le point visuel fort ; les détails
techniques restent accessibles à la demande. Les contenus restent alignés à
gauche, avec des lignes de lecture courtes et des titres hiérarchisés.

Tokens de référence, surchargés par le branding de chaque dossier : encre
`#17333c`, fond `#f4f7f8`, papier `#ffffff`, bandeau `#153f4a`, lien `#17687c`,
accent `#6ed5c2`. Les couleurs d’ontologie restent distinctes et accompagnées
de libellés. Segoe UI porte le texte, Bahnschrift les titres, avec les familles
locales configurées et leurs replis. Corps de lecture cible : 17 pixels.

```text
Projet : titre et intention de lecture
         dossiers et résultats attendus sourcés
         accès au récit, aux questions et au graphe

Graphe : titre, contexte exact
         angle de lecture et recherche
         filtres avancés repliés
         carte focalisée | objet et relation
         légende et sources
```

Après revue du plan, les dossiers de l’accueil deviennent une liste structurée
plutôt qu’une grille de cartes identiques. Les six parcours se répartissent sur
trois colonnes quand l’espace le permet. Le graphe commence par un voisinage
déclaré, sans présenter ce point de lecture comme un point d’entrée métier.

Les mouvements répondent à un changement de cadrage ou à l’ouverture d’une
déclaration. La lecture d’une relation suit manuellement ses deux objets et
son libellé ; elle ne simule ni message, ni appel, ni exécution métier. Aucun
défilement, musique ou lecture automatique. Le mouvement réduit donne l’état
final immédiatement. Les exports exacts et les couleurs du branding font autorité.

## État de l’incrément

**Reçu dans la portée locale le 4 octobre 2026**, dans le développement
0.35.0.dev1. Le site généré utilise cette présentation ; la maquette de l’audit
reste un document exploratoire distinct. L’accueil montre l’intention déclarée
du dossier avec un lien vers sa révision exacte, lorsqu’une intention ou un
objectif de son namespace est disponible. Sinon, il conserve la description
du dossier. Il ne reprend pas l’intention d’un autre namespace.

Le graphe propose Besoins, Solution, Données et Réalisation. Il s’ouvre sur un
voisinage déclaré et garde les filtres avancés repliés. Le lecteur parcourt
manuellement Source, Relation et Destination ; chaque étape permet d’examiner
la définition ou la déclaration exacte. Le cadrage dure 200 ms lorsque les
mouvements sont autorisés. Il donne immédiatement l’état final lorsque la
réduction des mouvements est demandée. Sans JavaScript, la carte interactive
reste masquée et les définitions ainsi que le JSON restent disponibles.

## Vérifications et revue visuelle

Les 48 tests locaux pertinents passent. Dans Edge isolé, les trois dossiers
Asteria ont parcouru quatre tailles, 320, 390, 768 et 1 440 pixels : 12 parcours
du graphe, 48 sélections d’angle, 60 étapes de lecture d’une relation et
72 parcours par public. Le clavier, la recherche vide, les filtres, la remise
à zéro, le cadrage animé et la réduction des mouvements ont été exercés.
Aucun débordement horizontal, erreur de page ou appel externe observé.

La carte commence à 535 pixels sur l’écran de 1 440 pixels et à 604 pixels
sur celui de 390 pixels, contre 927 et 1 529 pixels dans l’audit initial. À
320 pixels, elle commence à 654 pixels. Ces mesures concernent les dossiers
fictifs avec le branding AIR et une hauteur de fenêtre de 1 000 pixels ; elles
ne garantissent pas un premier écran identique avec tous les logos et titres.

La revue des captures a corrigé un en-tête mobile trop haut, des commandes
sur deux lignes et une carte initialement trop vide au-dessus des objets.
Les trois identités entreprise, consultant et studio passent 48 contrôles de
pages : noms, logos, couleurs, polices et couleurs d’ontologie conservés.

La PWA conserve ses 362 ressources épinglées : lecture des trois dossiers et
graphes hors ligne, mise à jour explicite, échec de mise à jour sans perte de
la version précédente, effacement limité à son périmètre. L’installation par
l’interface du système d’exploitation n’a pas été exercée. Les 206 pages
servent leurs octets exacts ; tous les liens locaux et fragments résolvent.
Le modèle source et les trois JSON de graphes sont identiques octet par octet
à UX01. La génération reste déterministe et sa réapplication idempotente.

Voir les preuves (document historique ou livrable local non inclus),
l’accueil (document historique ou livrable local non inclus), la
carte mobile (document historique ou livrable local non inclus) et la
lecture d’une relation (document historique ou livrable local non inclus).

## Portée et suite

La réception du connecteur UX00 reste ouverte : aucune nouvelle recette native
ChatGPT n’est annoncée. UX03, transmission aux équipes, puis UX04 et UX05
restent à réaliser. Zéro participant utilisateur, aucune certification
d’accessibilité et aucune CI exécutée. Les trois dossiers fictifs restent
`NOT_READY` avec leurs neuf tests métier originaux non exécutés. Leurs couleurs,
relations et mouvements expliquent des déclarations, sans prouver une
réalisation ou une exécution métier. La distribution publique rc9 reste distincte.
