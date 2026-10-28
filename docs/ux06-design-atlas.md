# UX06 : design Atlas et références techniques masquées

Le design Atlas devient la présentation par défaut du site de chaque projet
d'architecture. Il est porté par `src/air/assets/architecture-site.css` et par la
coquille commune `architecture_site.shell()`. Une simple régénération applique le
nouveau template à tout projet ; les données, pages, liens et parcours restent
identiques.

## Direction

- Un bandeau d'identité sombre en trame de plan, construit sur les couleurs `header`
  et `accent` du branding.
- Une navigation latérale en pastilles et une feuille de lecture surélevée, avec un
  rayon et une famille d'ombres uniques pour toutes les surfaces : dossiers, parcours,
  cartes du récit, colonnes de suivi, diagrammes et tableaux.
- Les mouvements accompagnent la lecture :
  - apparition courte du contenu ;
  - levée des cartes au survol ;
  - ouverture animée des déclarations ;
  - jauges d'avancement qui se remplissent.
- Aucune lecture automatique. La préférence de mouvement réduit supprime toutes ces animations.
- Les polices restent des familles installées : la politique de sécurité interdit
  le téléchargement de polices. Le branding garde l'autorité sur les couleurs et les
  polices, car `brand.css` est chargé après la feuille commune.
- Les couleurs d'ontologie, `--green` et la feuille BPMN épinglée ne changent pas.

## Références techniques

Les URN, identifiants d'objet, empreintes `sha256:` et sélecteurs JSON sont des
données d'audit. Par défaut, ils sont masqués et remplacés par une courte pastille :
« identifiant », « empreinte », « masquée » ou « sélecteur ». L'interrupteur
**Références techniques** de l'en-tête les affiche.

- **Aucune perte.** Les valeurs restent dans le HTML : la recherche locale, les tests,
  l'impression et l'export les conservent. L'impression les affiche toujours.
- **Sans JavaScript.** L'interrupteur est une case à cocher native avec son libellé,
  pilotée par CSS (`:has`). Le JavaScript ajoute seulement une préférence locale
  (`air-site-tech-refs`) pour garder le choix d'une page à l'autre, plus un repli
  pour les navigateurs sans `:has`.
- **Ce qui est masqué.** `architecture_site.tech_refs()` ne transforme que le texte
  visible. Les balises, attributs, scripts JSON, sources préformatées, options de
  liste et SVG gardent leurs octets.
- **Blocs de contexte.** Les blocs de contexte exact (`reading-context`,
  `dossier-context`, `capsule-context`) suivent le même interrupteur.
- **Pages construites en JavaScript.** Le graphe et la page des changements marquent
  de la même façon leurs lignes d'identité, d'empreinte et de sélecteur.

## Vérification

- `tests/test_site_tech_refs.py` couvre le masquage, les zones préservées et la coquille.
- Les suites du site existantes restent vertes.
- Revue dans le navigateur intégré sur la démonstration Asteria :
  - accueil, dossier, catalogue d'objets et graphe ;
  - interrupteur activé et désactivé, préférence conservée entre les pages ;
  - aucune erreur de console, aucun débordement horizontal à 320 et 390 pixels.
