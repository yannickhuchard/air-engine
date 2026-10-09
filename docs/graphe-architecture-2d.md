# Explorer les dossiers en 2D

Disponible dans le développement **0.35.0.dev1**, cet incrément A04 ajoute un
graphe interactif à chaque dossier du [site statique](site-architecture-statique.md).
Depuis l’accueil du projet, ouvrir un dossier puis « Explorer le graphe 2D ».
Il fonctionne hors ligne, sans serveur ni bibliothèque à installer pour le lire.

## Lire et naviguer

Depuis UX02, choisir Besoins, Solution, Données ou Réalisation ouvre un
voisinage pertinent pour cette lecture. Le point sélectionné facilite le
cadrage ; il ne constitue pas un point de départ métier calculé. Les filtres
avancés sont disponibles dans « Ajuster les objets, parcours et relations ».
Voir la [réception locale et ses limites](ux02-design-et-lecture-graphe.md).

Les couches suivent l’ontologie : besoins et acteurs, fonctions et processus,
contrats et échanges, composants et implantation, données et ontologie, choix et
réalisation, sources et vérification. Chaque objet affiche son type et sa
révision. Les étapes d’un workflow ont une forme arrondie ; elles restent des
déclarations locales de leur workflow, pas de nouveaux objets du registre.

La recherche filtre les noms, types et descriptions, sans distinction d’accent
ou de casse ; tous les mots saisis doivent être présents. Les sélecteurs de type,
couche et relation permettent de réduire le dessin. Les couches de gouvernance
et de preuves, ainsi que les références de périmètre, provenance et composition,
sont masquées au départ pour faciliter la lecture ; elles restent sélectionnables.

Choisir un objet ouvre sa description, ses voisins directs et sa définition
exacte. Le panneau conserve aussi les relations masquées par les filtres. Le
mode « Voisins seulement » limite le dessin aux relations directes des types
actifs ; il ne calcule pas une chaîne métier transitive. Cliquer une relation
affiche son objet source, sa révision, son empreinte, son sélecteur et, pour les
projections de flux, connexion ou branche, sa déclaration complète.

Une relation se lit manuellement en trois étapes, Source, Relation et
Destination. Le cadrage accompagne l’étape choisie, sans simuler un message ou
un appel. Les mouvements peuvent être désactivés et respectent la préférence
de réduction des mouvements du navigateur.

Un parcours A02 peut être mis en évidence, avec option pour ne conserver que
son contexte. La surbrillance représente les objets associés et les étapes des
workflows référencés, avec les points de vigilance du parcours. Elle ne prouve
ni causalité ni chaîne d’appels. La page dédiée du parcours donne les branches,
gardes et lacunes détaillées.

La caméra initiale conserve des libellés lisibles ; une miniature donne la vue
globale. Cliquer dans cette miniature déplace le cadrage. Les boutons agrandissent,
réduisent, cadrent l’ensemble ou centrent l’objet choisi ; glisser le fond déplace
la vue. Une sélection dans un dessin inchangé conserve le cadrage. « Réinitialiser »
rétablit les filtres et la caméra initiale.

Au clavier : Tab parcourt les contrôles, objets et relations ; Entrée ou Espace
ouvre le panneau et place le focus sur son lien source. Sur le canevas, les
flèches déplacent et +/− changent le zoom. Échap efface la sélection. Sur écran
étroit, le panneau passe sous le dessin. Sans JavaScript, la liste des objets,
les définitions et le JSON restent consultables.

## Sens des flèches et sources

Le moteur `air.graph-explorer/1` produit une projection déterministe d’**une
baseline exacte**. Chaque objet et chaque slot de référence de cette baseline
est conservé ; les révisions et dossiers divergents ne sont pas fusionnés.
Une référence manquante est signalée, sans créer un objet accessible fictif.

| Relation | Ce que la déclaration permet de lire |
| --- | --- |
| Référence, périmètre, provenance | Lien déclaré vers un autre objet ; trait discontinu, sans interaction métier inférée |
| Réalisation, opération de contrat, fonction d’étape | Association déclarée, sans preuve d’appel ou de fonctionnement |
| Flux de données | Direction source → destination explicitement portée par un DataFlow |
| Connexion prévue | Topologie portée par Connection ; elle ne devient pas un flux métier |
| Relation de concepts | Sujet → objet, prédicat et cardinalité déclarés, sans multiplicité inverse inventée |
| Branche de workflow | Transition potentielle ; garde et condition conservées, non évaluées par le dessin |
| Étape du workflow | Composition locale du workflow |

Les jointures parallèles, autorisations, erreurs et compensations ne sont pas
reconstruites par une disposition graphique. Lire le parcours et les déclarations
pour ces mécanismes. Le graphe n’exécute aucune solution métier et n’accorde
aucune autorisation. Les droits sont contrôlés lors de la compilation du site ;
un export statique ne réévalue pas les droits de ses lecteurs.

Le fichier `graph.json` possède les nœuds, relations, sources exactes, lacunes,
légende et `graph_digest`. Le JSON embarqué dans `graph.html` conserve cette même
projection ; les liens de présentation et les parcours sont dans une enveloppe
séparée. L’empreinte ne dépend donc pas des chemins HTML.

## Budgets et réception

La projection refuse explicitement au-delà de **1 000 objets par baseline,
4 096 nœuds avec étapes ou 16 384 relations**. Les budgets du site et du pack
s’appliquent aussi : 4 MiB par ressource et 16 MiB par pack. Réduire le périmètre
ou demander `website: false` pour un export sans site ; aucune troncature
silencieuse de la projection n’est acceptée.

Le dessin est limité à **180 nœuds et 1 000 relations** correspondant aux filtres.
Les compteurs signalent les éléments non dessinés ; l’objet choisi et les membres
du parcours sont prioritaires. Le panneau présente au plus 200 relations directes,
avec avertissement. Le JSON conserve toutes les relations autorisées. Ces bornes
de lecture ne certifient pas la lisibilité d’un grand dossier complexe.

Les parcours précompilés suivent la limite du site de 64 racines Workflow,
CustomerJourney ou ValueStream par dossier ; la CLI/API/MCP permet une sélection
exacte distincte selon le [contrat des parcours](parcours-metier-sources.md).

Réception locale : trois dossiers Asteria, filtrage, contexte de parcours,
sources, clavier, déplacement, caméra et miniature, écran étroit, liens et
rendu sans réseau. Les neuf cas métier restent NOT_EXECUTED et les portes
NOT_READY ne sont pas maquillées. Voir le
reçu du 3 octobre (document historique ou livrable local non inclus).

Ce lot livre la **2D par dossier**. Un incrément suivant ajoute les
[comparaisons d’états et dates déclarées](comparaison-temporelle-site.md).
Le graphe fusionné inter-dossiers, sa navigation générale par le temps et la 3D
restent à réaliser ou à évaluer. AMASE reste un mapping
pour discussion ; ni profil intégré, ni nouvelle qualification des clients
natifs, du plugin soumis ou de la distribution publique rc9 n’est revendiquée.
