# Barre de complétude du Projet d’architecture

Exercice UX/UI avant implémentation, 10 octobre 2026. Cette étude est une
évaluation de conception ; aucune séance avec des utilisateurs réels n’est déclarée.

## Besoin et parcours

L’architecte doit trouver le prochain manque utile sans parcourir 37 pages.
Une équipe de réalisation doit distinguer un contenu disponible d’une vérification
restante. Le management doit comprendre pourquoi un dossier bien documenté peut
encore être non prêt à construire.

Parcours : ouvrir l’accueil, repérer une partie, ouvrir ses détails, lire les
manques et le travail déclaré, puis accéder au sujet exact ou à sa question.
Le site demeure statique : une modification du registre exige sa régénération.

## Variantes examinées

1. Une jauge globale : compacte, mais masque les manques critiques et mélange
   couverture documentaire et réception. Écartée.
2. Trente-sept petits segments : complet, mais illisible au toucher et sur mobile.
   Écartée pour l’accueil ; les sujets restent accessibles dans les détails.
3. Huit parties nommées, une courte jauge par partie et des détails au clic :
   retenue. Chaque sujet appartient exactement à une partie. Aucun ordre de
   construction n’est suggéré par leur position.

```text
Avancement du dossier                     Préparation : 10/12
[Intention 80%] [Expérience 67%] [Architecture 50%] ...
               clic
Expérience : 2 sujets sur 3 documentés ou calculés
Renseigné | À compléter | Contrôles restants | Travail déclaré
Sources et liens vers les sujets concernés
```

Les valeurs ci-dessus illustrent la maquette, pas une mesure d’un dossier.

## Contrat de mesure

Pourcentage = partie entière de 100 × sujets SOURCES_PRESENT ou CALCULATED /
nombre de sujets présents dans cette partie. PARTIAL et NOT_DOCUMENTED ne
comptent pas comme couverts. Le numérateur et le dénominateur sont visibles.
Une partie sans sujet affiche « Non évalué », jamais 100 %.

Le calcul mesure la couverture documentaire de la projection existante,
pas le pourcentage d’effort réalisé, la complétude sémantique ou une approbation.
Une couverture de 100 % peut conserver des contrôles NOT_MET.
Les états en cours viennent exclusivement de déclarations IN_PROGRESS ou
INVESTIGATING, jamais d’une estimation depuis le pourcentage. Une tâche n’est
rattachée à une partie que par ses livrables exacts ; le travail non rattaché
reste visible séparément. DONE ne qualifie pas une preuve.

## Direction visuelle et interaction

Réutiliser les couleurs et fontes du branding AIR, avec fond de jauge neutre,
accent de marque pour la couverture et texte explicite pour les blocages.
Pas de couleur différente pour chaque partie. Une bande compacte à huit
segments sur grand écran, quatre colonnes sur tablette et deux sur mobile.
Les boutons restent assez grands pour le toucher ; titres et fractions lisibles.
Un seul panneau ouvert par composant. Animation limitée à l’interaction,
désactivable par la préférence de mouvement réduit.

Le balisage natif details/summary offre un fonctionnement sans JavaScript.
Le clavier, le focus, l’ouverture/fermeture, les liens et les lecteurs d’écran
restent utilisables. Plusieurs dossiers possèdent des composants indépendants.

Références de conception :
[visibilité de l’état, Nielsen Norman Group](https://www.nngroup.com/articles/visibility-system-status/)
et [disclosure, W3C WAI](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/).

## Réception prévue

Vérifier les manques explicites, une partie vide, 100 % documentaire avec gate
ouverte, les tâches liées/non liées et les inconnues en investigation. Vérifier
les trois dossiers Asteria, 320/390/768/1440 px, clavier, mouvement réduit,
absence de JavaScript, PWA et absence de réseau externe. Conserver les preuves.
La compréhension par des personnes réelles reste un essai distinct à organiser.
