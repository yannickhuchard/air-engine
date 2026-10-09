# Site statique des dossiers d’architecture

Disponible dans le développement 0.35.0.dev1, distinct de la distribution publique
rc9. Chaque compilation complète de `deliverables` génère par défaut
`livrables/site/index.html` et `livrables/architecture-model.json`.

Chaque dossier comprend aussi son [architecture story](architecture-story.md),
en six chapitres sourcés, avec une lecture courte de 24 secondes. Les vidéos
BRAG/Hyperframes sont des compagnons optionnels ; le site et sa PWA restent
générés avec Python seul.

La checklist et le kanban figurent en fin de l’accueil du projet et de chaque
dossier. `progress.json` expose l’épingle exacte, les sujets documentés ou
partiels, les critères calculés et les inconnues ouvertes avec leurs sources.
Les quatre colonnes sont « À documenter », « À compléter », « À valider » et
« Documenté ou calculé ». Une présence de source n’est pas une approbation et
un site statique s’actualise par régénération après une nouvelle baseline.
La lecture et le suivi ne dépendent pas de JavaScript.

Le pack reste borné à 16 MiB par défaut. Une requête de génération peut choisir
explicitement `max_total_bytes` entre 16 et 64 MiB, par exemple `33554432` pour
32 MiB. Les limites par fichier restent actives. La CLI reçoit le pack complet
avec un budget de transport proportionné et borné pour l’expansion JSON ;
les agents MCP demandent `content: DIGESTS`, puis les sujets nécessaires.
Les projections JSON sont compactées sans supprimer les objets, liens ou
octets des artefacts retenus. Les fiches de transmission donnent accès à la
déclaration complète par son lien exact dans le catalogue d’objets.

Le dossier ProxiBot (document historique ou livrable local non inclus) démontre le suivi sur
une conception de livraison locale par robots, avec inconnues métier conservées.

UX02 améliore [la présentation et la lecture du graphe](ux02-design-et-lecture-graphe.md)
dans le générateur : accueil avec intentions sourcées, quatre angles de lecture,
voisinage initial et parcours manuel source/relation/destination. Les commandes
de cadrage sont animées lorsque le lecteur l’autorise ; les couleurs
d’ontologie, les modèles exacts et la PWA sont conservés.

UX03 fournit [la transmission aux équipes](ux03-transmission-equipes.md) :
`handoff.html` et `handoff.json`, fiches par bloc logique, composant
d’implantation, unité de construction et équipe déclarée. Chaque fiche relie
contrats, données, dépendances, responsabilités, critères, vérifications et
jalons avec leurs sources exactes. Son diagramme dispose d’une page de focus.
Les manques restent visibles et aucune affectation n’est déduite du propriétaire
du document ou d’une RACI sans sujet.

UX04 ajoute [la coopération site/agent](ux04-cooperation-site-agent.md) :
`cooperate.html`, un éditeur local de question et 37 capsules JSON de départ
par dossier. Choisir un public, sélectionner des sources exactes et télécharger
ou copier la demande. Le site ne lance aucune connexion ni dépôt. La page reste
accessible hors ligne avec sa présélection de sujet et de public ; les capsules
de départ sont accessibles sans JavaScript. Le MCP `air_resume_question` et la
CLI `question-resume` vérifient le contexte du registre actuellement connecté.

L’incrément A02 ajoute [les parcours métier sourcés](parcours-metier-sources.md) :
recherche locale et pages de focus par workflow/parcours utilisateur/chaîne de
valeur, avec étapes, gardes, lacunes, sources exactes et JSON. Les références
associées ne sont pas transformées en causalité.

L’incrément A04 du 3 octobre ajoute un [graphe 2D](graphe-architecture-2d.md)
par baseline : filtres par couche/type/relation, voisins directs, sources exactes,
contexte des parcours, zoom et miniature globale. Le JSON sémantique est fourni
avec chaque graphe ; les filtres de lecture ne modifient pas le registre.

La [page des changements et dates](comparaison-temporelle-site.md) ajoute les
comparaisons de paires exactes explicitement choisies, la validité déclarée
filtrable par frontière et le calendrier de Milestone/Roadmap prévu. Ces lectures
ne deviennent pas une reconstruction historique ni une preuve de réalisation.

## Lecture

L’accueil du projet réunit les baselines choisies. Un dossier possède sa propre
version, son récit de conception et ses sources : aucune révision divergente n’est
fusionnée dans ses pages. Les sections suivent le besoin, la valeur, les parcours,
les mécanismes, l’ontologie, les décisions et conséquences, puis les écarts et la
préparation de la réalisation.

Chaque dossier comporte les **37 sujets du catalogue**, même lorsqu’un sujet n’est
pas encore documenté. Dans ce cas la page dit ce qui manque. Chaque diagramme
produit possède une page dédiée, une légende, sa source et des boutons de zoom.
Les objets reliés des graphes mènent à leur définition exacte ; les autres restent
accessibles dans les listes de sources. Les tables et noms demeurent consultables
sans JavaScript ; le dessin SVG nécessite JavaScript dans le navigateur.

Les explications viennent des intentions, objectifs, parcours, raisons,
conséquences, hypothèses et inconnues déclarés. Aucun LLM n’est nécessaire pour
les compiler. Une absence de décision n’est pas comblée par un récit inventé.

Le site utilise des pages et ressources locales ; pas de serveur, CDN, Node ou
accès cloud requis pour l’utiliser. Mermaid Tiny **12.1.0** est inclus, sous MIT,
avec licence, origine et empreinte. Le rendu est configuré en mode strict selon
la [documentation officielle Mermaid](https://mermaid.js.org/config/usage.html).
La politique du site limite les connexions à la même origine pour sa PWA et
bloque objets et formulaires ; le
texte du modèle n’est jamais interprété comme HTML ou code de l’agent.

L’[atlas responsive et la PWA](site-responsive-pwa.md) modernisent la lecture,
replient la navigation sur mobile et permettent une conservation explicite
hors ligne via un serveur de boucle locale Python. Le mode fichier direct reste
disponible. Le modèle exact figure aussi dans le site, en JSON compact ; les
pages et exports du site restent disponibles depuis la copie PWA.

## Génération avec un IDE

Préparer une requête JSON contenant le titre et les baselines exactes autorisées :

```json
{
  "title": "Projet de transformation",
  "baselines": [
    {"id": "urn:entreprise:baseline:solution", "revision": 1, "digest": "sha256:<empreinte exacte de 64 caractères>"}
  ]
}
```

L’empreinte de cet exemple est un placeholder, pas une baseline utilisable.
Depuis une installation AIR démarrée, l’IDE récupère les références exactes,
enregistre la requête et utilise le parcours existant :

```powershell
.venv/Scripts/python.exe -m air deliverables requete.json --workspace D:/architecture/projet --apply --credential architect.json
```

Le fichier d’identité est lu par le programme, jamais affiché. Sans `--apply`, la
CLI présente le plan. La génération protège les fichiers modifiés à la main et
conserve le manifeste des empreintes. Ouvrir ensuite
`D:/architecture/projet/livrables/site/index.html` et transmettre le dossier
complet si ses destinataires sont autorisés à consulter ces données.

API : `POST /v1/deliverables/compile`. MCP : `air_compile_deliverables` avec
`content: "DIGESTS"` pour contrôler la génération et lire l’index du site. La
réponse HTML complète est volontairement trop grande pour une conversation ;
utiliser la CLI pour les fichiers. `only` conserve les lectures ciblées sans
site ; `website: false` permet explicitement un pack sans site. Les exports de
modèle accompagnent aussi les sélections des sujets 18, 19 ou 20.

## Modèles exacts et limites

`architecture-model.json` conserve les snapshots séparés, tous leurs objets,
empreintes, verrou de dépendances, schémas des types présents et octets des
artefacts DataSchema autorisés en base64. Les sources externes restent des
références : elles ne sont pas téléchargées. Les cardinalités déclarées,
identités et attributs sont exposés dans le modèle logique ; les colonnes,
nullabilité et références exactes dans le modèle physique.

Le pack exporte **ce qui est déclaré**. Il ne complète pas les contraintes
d’entité actuellement non prises en charge, ni les comportements de stockage,
DDL, migrations, UNIQUE/CHECK ou cardinalités inverses absentes. Les types et
index physiques demeurent des déclarations. Les documents Markdown de synthèse
multi-dossiers gardent leur sélection historique par plus haute révision ; leurs
divergences sont maintenant signalées. Les pages et Markdown de chaque dossier,
ainsi que le JSON exact, conservent leurs propres révisions.

Les budgets restent explicites : 16 baselines, 20 000 objets cumulés, 8 MiB
d’artefacts de schémas cumulés, 4 MiB maximum par page/ressource du site et 16 MiB
pour le pack. Un dépassement refuse la compilation ; réduire le périmètre au
lieu d’omettre des objets. Les droits du registre et des artefacts sont contrôlés
à la génération ; ils ne sont pas réévalués quand le site statique est ouvert.

Le graphe possède aussi ses [budgets explicites](graphe-architecture-2d.md) :
1 000 objets par baseline, 4 096 nœuds avec étapes et 16 384 relations ; le dessin
limite la lecture à 180 nœuds et 1 000 relations, avec compteurs et JSON complet.

Ce site ne qualifie pas de nouveau client natif et n’intègre pas le profil AMASE.
Les requêtes A02 restent dans leurs baselines distinctes. Les comparaisons d’états
et dates déclarées sont livrées ; la vue fusionnée inter-dossiers, la navigation
générale d’un graphe par le temps et la 3D restent à réaliser.
Voir la [roadmap](roadmap-modeles-parcours-site.md).

## Démonstration et réception locale

```powershell
.venv/Scripts/python.exe scripts/demo_architecture_site.py
```

Cette commande crée un registre SQLite neuf dans `tmp`, puis le site du projet
Asteria avec trois dossiers fictifs : SAV, atelier et identités. Les modèles
ajoutés sont des designs déclarés, sans exécution de la solution métier. Le
profil choisi pour le stockage de la solution est un exemple PostgreSQL à
évaluer ; AIR lui-même reste installé avec SQLite.

La vérification navigateur facultative utilise Node/Playwright uniquement en
développement. La réception locale et les empreintes figurent dans le
reçu (document historique ou livrable local non inclus). Les trois parcours
DEMO-METIER-1 sont rejoués séparément. Les neuf tests métier non exécutés et les
portes bloquées restent visibles, sans nouvelle attestation de conformité AIR.


## Dimension financière et traçabilité standard

Chaque dossier et son accueil donnent accès à `finance.html` / `finance.json` et `traceability.html` / `traceability.json`. Le sujet 17 développe les calculs de chaque poste ; le Sankey possède une page de focus, un filtre et ses preuves textuelles. Les absences restent explicites. Voir [le contrat et la décision UX](dimension-financiere-et-sankey.md). Les approbations de référence, les fonds, les sorties déclarées et la production prévue gardent des statuts distincts.

## Parcours par persona

`journeys.html/json` inventorie les parcours de tous les personas déclarés,
avec contacts et usages numériques, physiques et géographiques. Une page de
focus est produite par parcours. Le catalogue est accessible depuis l’accueil
et la navigation ; le filtre fonctionne au clavier et les listes restent
complètes sans JavaScript. Les cinq contrôles de couverture apparaissent dans
la checklist, le kanban, le sujet 03 et la matrice 34. Les dossiers historiques
sans catalogue conservent leurs parcours et leurs lacunes explicites.
Voir [le contrat et les limites](parcours-personas-et-usages.md).
