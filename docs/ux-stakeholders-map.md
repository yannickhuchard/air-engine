# Une carte pour comprendre et mobiliser

## Exercice de conception

Le lecteur cherche une contribution, comprend pourquoi elle est nécessaire, puis
identifie la prochaine action. Le management repère les rôles manquants ;
l'architecte retrouve les responsabilités, le RACI et les éléments concernés.
Sur téléphone, la même lecture doit rester possible avec le pouce et sans
déplacer un diagramme horizontal. Il s'agit d'une revue heuristique et d'une
recette technique, pas d'une étude auprès d'utilisateurs ni d'une mesure
d'ergonomie optimale.

Le premier essai utilisait quatre colonnes SVG de largeur fixe puis une longue
liste de fiches. Il séparait la sélection de son explication. L'aperçu dans la
conversation utilisait des boutons trop arrondis et peu structurés. Aucun des
deux ne donnait une hiérarchie satisfaisante entre rôle, personne et action.

## Direction retenue avant réalisation

- Palette : encre #17333c, papier #ffffff, fond #f1f6f7, accent #17687c ;
  états #16735d, #255ca8, #a13c26 et #655578, avec libellés explicites.
  Les couleurs structurelles et la police héritent du branding AIR.
- Typographie : Segoe UI pour la lecture, Bahnschrift pour les titres si
  disponible. Aucun téléchargement de police nécessaire.
- Composition : une carte de contributions, reliée visuellement au projet,
  et une fiche de lecture. Alignement à gauche, titres courts, personnes
  distinctes des rôles. Les surfaces sélectionnées utilisent un repère
  discret et un état textuel, sans gros aplat qui masque les informations.
- Interaction : filtres par état, recherche locale, sélection à la souris,
  au toucher et au clavier. Une seule fiche détaillée en mode interactif,
  liens profonds conservés et toutes les fiches accessibles sans script.
- Mouvement : une courte transition de sélection, aucune animation en boucle,
  respect de la préférence de réduction du mouvement.

```text
Ordinateur
  Projet d’architecture
  États filtrables + recherche
  Contributions regroupées          Fiche sélectionnée
  Rôle / personne / état             Pourquoi / responsabilité / action
                                    RACI / éléments concernés / source

Téléphone
  Carte : projet / états filtrables / recherche / contributions empilées
    sélection d'un rôle
  Fiche dédiée : contribution / action / sources / retour à la carte
```

## Relecture du parti pris

Un graphe en réseau force-dirigé rendrait difficile la comparaison des états
et inventerait une importance que le modèle ne mesure pas. Une grille de
statistiques ajouterait de la décoration sans aider à mobiliser quelqu'un.
La carte garde donc des groupes lisibles et donne la place principale au rôle,
puis à sa contribution. Le compte porte sur les contributions, pas sur un nombre
de personnes uniques. « À préciser » ne signifie pas « poste vacant ».

## Critères de réception

Pas de débordement horizontal à 320, 390, 768 et 1440 pixels. Recherche et filtres
combinables, état sélectionné explicite, liens profonds et retour fonctionnels,
cibles tactiles d'au moins 44 pixels, textes longs sans troncature, sources
toujours accessibles. Lecture complète sans JavaScript et à l'impression.
Les résultats réellement exécutés sont conservés dans le reçu de traçabilité.

La critique du premier rendu de cette refonte a conduit à supprimer les marges
héritées entre groupes et à remplacer l'empilement carte + fiche sur téléphone
par deux vues. Le retour conserve les filtres, la recherche et le rôle actif.
