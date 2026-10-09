# Processus et cartes d’expérience

## Choix de formats

| Besoin | Format livré | Motif et limites |
| :--- | :--- | :--- |
| Processus, participants, conditions et branches | BPMN 2.0 descriptif, bpmn-js 18.16.0 | Couloirs, activités, événements et gateways ; XML avec positions et points de passage. Aucun moteur d’exécution BPMN. |
| Parcours d’un persona et expérience du service | Customer Journey Map complétée par un service blueprint, HTML/SVG | Matrice par étape, acteurs, touchpoints, lieux, pensées, émotions et systèmes. Aucun standard ISO de conformité UX revendiqué. |
| Source documentaire compacte des processus | Mermaid flowchart en couloirs | Source Markdown secondaire, liée aux mêmes objets. Mermaid Tiny local utilise Dagre ; ELK n’est pas livré dans ce bundle. |
| Diagrammes d’autres sujets d’architecture | Mermaid local existant | Les autres vues conservent leur format et leurs sources. |

La spécification [BPMN 2.0.2 de l’OMG](https://www.omg.org/spec/BPMN/2.0.2/)
définit la notation et ses échanges XML. [bpmn-js](https://bpmn.io/toolkit/bpmn-js/)
importe ces diagrammes dans le navigateur. AIR calcule et conserve le layout
dans le BPMN DI : il ne dépend pas d’un placement aléatoire du lecteur.

Le [journey de Mermaid](https://mermaid.js.org/syntax/userJourney.html)
décrit des tâches avec acteurs et scores de 1 à 5. Il est trop compact pour
porter seul notre carte d’expérience. Les [journey maps de NN/g](https://www.nngroup.com/articles/journey-mapping-101/)
et les [service blueprints](https://www.nngroup.com/articles/service-blueprints-definition/)
motivent la séparation entre expérience du persona, service visible,
actions internes et support. AIR en propose une présentation adaptée aux
dossiers d’architecture, sans prétendre avoir réalisé une recherche utilisateur.

## Carte complète et schéma agentique

CustomerJourney accepte `view_state` (AS_IS ou TO_BE) et `scenario`.
Chaque étape peut documenter `phase`, `action`, `thoughts`, `frontstage`,
`backstage`, `support_processes`, `systems`, `duration`, `opportunities` et
`emotion`, en plus des contacts, acteurs, usages, irritants et résultat existants.
Les systèmes sont des références exactes vers RuntimeComponent,
ArchitectureBlock ou Device. Les autres associations de blocs restent
distinctes : elles n’infèrent pas un appel technique.

Une émotion comporte un `status` UNKNOWN, HYPOTHESIS ou OBSERVED. Un état
inconnu ne peut avoir de label ou de score inventé. Une hypothèse porte label
et rationale ; une observation porte aussi des sources exactes Source ou
Assertion. Un score facultatif de 1 à 5 va de très négatif à très positif.
Une déclaration OBSERVED n’est pas une certification automatique des sources.

```json
{
  "phase": "Retirer le colis",
  "action": "Ouvrir le compartiment après contrôle du code",
  "thoughts": ["Hypothèse à discuter : vérifier que le bon colis est disponible"],
  "frontstage": ["Présenter la marche à suivre et le résultat du contrôle"],
  "backstage": ["Vérifier l’autorisation de remise"],
  "support_processes": ["Conserver une preuve minimale de la remise"],
  "opportunities": ["Rendre le repli humain accessible depuis le point de remise"],
  "emotion": {
    "status": "HYPOTHESIS",
    "label": "Attente de confirmation",
    "score": 3,
    "rationale": "Proposition de conception à examiner avec les destinataires"
  }
}
```

Cet extrait complète une étape, pas un objet importable seul. Lire le schéma
avec `air_describe_type`, ajouter les références réelles, valider et rebaser,
puis déposer et figer dans la portée autorisée. Les schémas CLI et MCP sont
identiques. Les révisions historiques restent immuables.

La carte montre toujours quatorze dimensions. Les inconnues restent visibles
et la courbe ne relie pas des scores séparés par une inconnue ou des statuts
d’observation différents. Sans score, aucune courbe artificielle n’est créée.
Le comptage `experience_missing` reste distinct des cinq contrôles des liens
et des douze critères readiness. Il ne les transforme pas en validation UX.

Le desktop utilise une matrice à en-têtes fixes, défilement et légende.
Le mobile propose d’abord des fiches par étape avec les mêmes dimensions,
puis la comparaison horizontale. Tout le contenu reste lisible sans JavaScript.

## Diagramme visuel interactif - 8 octobre 2026

Chaque parcours possède aussi une page `journey-map-*.html`, un SVG portable
et un JSON lié à la même baseline. La carte SVG présente l’ordre des étapes,
les phases, les contacts et contextes d’usage, les acteurs, les systèmes
explicitement affectés et le ressenti. Les blocs associés restent distincts
des appels techniques. Les libellés peuvent être abrégés dans le dessin ; les
fiches et les sources conservent leurs détails complets.

Le JavaScript local permet de sélectionner une étape, utiliser les flèches du
clavier, filtrer par intervenant, mettre en évidence une dimension, ajuster le
zoom et lancer ou arrêter une visite guidée. La sélection ouvre les quatorze
dimensions de la fiche correspondante. La matrice comparative reste disponible
en complément. Les vues de sujet proposent une carte compacte avec accès au
diagramme dédié ; les pages de focus présentent aussi les fiches.

La visite illustre uniquement l’ordre déclaré : elle n’exécute pas la solution
et ne simule pas son comportement métier. Le mouvement répond aux actions du
lecteur, respecte sa préférence de mouvement réduit, et la visite s’arrête
quand la page est masquée. Sans JavaScript, le SVG, ses liens et les fiches HTML
restent disponibles. Aucun React, build Node, CDN ou service externe n’est
requis pour consulter le site. Les assets et exports entrent dans le manifeste
et la copie PWA. Le SVG autonome reprend les couleurs et la famille de police
locale du branding ; aucun chargement de police distante n’est ajouté.

Les inconnues ne deviennent ni un score neutre, ni une courbe inventée. Une
émotion sans score conserve son label et son statut. Les observations et
hypothèses ne sont pas reliées dans un même segment de courbe.
Les preuves de cet incrément (document historique ou livrable local non inclus)
distinguent tests locaux, essais de navigateur et recherche utilisateur non
réalisée.

## Processus et échanges BPMN

Le site produit `processes.html`, puis une page, un JSON de layout et un
fichier `.bpmn` par Workflow. Les sujets 04 et leurs pages de diagramme
utilisent cette même vue ; le sujet 03 et ses pages de diagramme utilisent
la carte d’expérience, pas une chaîne de rectangles.

Les couloirs regroupent les tuples exacts de participants. Ils ne les
assimilent pas à des responsables RACI. Les cycles sont condensés pour calculer
les colonnes puis conservés avec leurs retours. Les activités, les branches
et les références de fonction restent intégrales dans les listes de focus.
Les libellés longs du dessin peuvent être abrégés ; le détail complet reste
dans les listes et les sources.

Les splits décrivent les flux admissibles avec une gateway inclusive.
Les arrivées ANY utilisent une gateway exclusive de convergence, ALL une
gateway parallèle. Les gardes AIR sont conservées dans la documentation des
flux : elles ne sont pas converties en expressions d’un moteur BPMN.
La politique de terminaison et les fonctions de compensation restent dans
la documentation du processus. Les fonctions ne deviennent pas des événements
de compensation BPMN par inférence. `isExecutable=false` reste explicite.
La validité XML ne démontre pas l’équivalence de sémantique avec un moteur tiers.

Le lecteur est épinglé et embarqué, avec licence, provenance et watermark
bpmn.io visible. Aucun CDN, build Node ou accès réseau n’est requis à
l’installation ou à la consultation. Node et Chrome servent uniquement à la
recette visuelle facultative. Un SVG statique complet reste disponible si le
lecteur échoue ou si JavaScript est désactivé. Les nouveaux fichiers participent
au manifeste PWA et à ses empreintes.

## ProxiBot et réception

Le site ProxiBot r19 est régénéré depuis la même baseline, sans changement du
design ou des entrées des sept simulations. Ses contacts, acteurs et blocs
existants sont conservés. Les émotions, pensées et séparations frontstage /
backstage absentes ne sont pas inventées : elles sont à documenter lors des
ateliers d’expérience. Le score readiness reste 10/12.

Trois dossiers Asteria fictifs exercent des cartes enrichies, dont une émotion
inconnue au milieu du parcours. Toutes les émotions renseignées de cette
démonstration sont HYPOTHESIS, jamais une observation fabriquée.
Voir les preuves de réception (document historique ou livrable local non inclus).
