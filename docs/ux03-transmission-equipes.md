# UX03 : préparer la transmission aux équipes

## Direction avant implémentation

Chaque dossier fournit un accès « Préparer la réalisation », avec une fiche
par bloc logique, composant d’implantation et unité de construction, puis une
fiche par équipe déclarée. Le lecteur part de ce qu’il doit comprendre ou
construire, et retrouve les contrats, données, dépendances, responsabilités,
critères et vérifications sans parcourir les 37 sujets.

La fiche commence par son sujet et les questions ouvertes. Un sommaire court
donne accès aux sections. La représentation du périmètre s’appuie sur les
déclarations exactes ; les diagrammes existants restent accessibles par des
liens de focus. Les couleurs et les polices suivent le branding du dossier.
Le rendu reste utilisable sans JavaScript, en lecture directe et dans la PWA.

La projection utilise une seule baseline exacte, jamais la dernière révision
connue hors de cette baseline. Elle conserve des sélecteurs pour les liens
suivis. Une relation de réalisation ne prouve ni une livraison ni un ordre de
développement. Un contrat requis est une dépendance déclarée, pas une chaîne
d’appels calculée. Les RACI sans sujet restent générales ; une équipe n’hérite
pas d’une responsabilité en raison de son nom, d’un parent ou du propriétaire
d’un objet. Les résultats de vérification consignés restent distincts des cas
prévus et de leur méthode ou niveau de preuve.

Les dimensions non documentées portent une prochaine action : confirmer les
contrats, répartir les activités avec les équipes, préciser critères et tests,
convenir des jalons, niveaux de qualité et conditions de reprise. Aucun budget,
responsable, délai ou engagement implicite ne sera créé.

## État

**Reçu dans la portée locale le 4 octobre 2026**, dans le développement
0.35.0.dev1. Les packs complets produisent `handoff.html` et `handoff.json`
par dossier. Le menu « Préparer la réalisation » et le parcours des équipes de
réalisation donnent accès aux fiches. Chaque fiche comporte neuf sections et
un diagramme avec sa page dédiée. Les libellés des flèches facilitent la lecture ;
les sélecteurs exacts des déclarations sont conservés dans le JSON.

Les limites par dossier sont 1 000 objets, 128 fiches de composant/unité et
64 équipes. Le diagramme de focus se limite à 24 objets et 48 liens, avec une
mention lorsque ce cadrage réduit le dessin. Les fiches et le JSON conservent
leurs associations ; les limites de taille du pack restent applicables.

## Vérification locale

55 tests pertinents passent. Ils couvrent les sources et empreintes exactes,
les deux révisions d’une identité, la distinction entre contrat requis et
travail du consommateur, les RACI générales, les équipes présentes ou absentes,
la différence entre oracle prévu et résultat consigné, les références manquantes,
les textes actifs échappés, les limites et l’absence de modification des sources.
Les métadonnées canoniques ont été complétées dans les petits jeux de test
après leurs premiers échecs. Les contrôles finaux passent sur un répertoire de
test isolé ; les premiers essais ne sont pas des résultats de réception.

Les trois dossiers Asteria produisent 15 fiches de composant/unité et 15 nouveaux
diagrammes, soit 63 diagrammes au total. Ils ne contiennent aucune équipe
déclarée : cet état est expliqué dans l’index, sans attribution inventée. Les
pages d’équipe présentes sont vérifiées par les tests locaux ; aucune page
d’équipe n’a été exercée au navigateur dans cette démonstration Asteria.

La recette navigateur vérifie 60 lectures de fiches sur 320, 390, 768 et
1 440 pixels : sections, manques, ancres clavier, déclarations dépliables,
diagrammes et liens vers les définitions. La lecture sans JavaScript conserve
les sections et la source des diagrammes. Aucun débordement horizontal, appel
externe ou erreur de page observé. Sur mobile, agrandir le diagramme permet de
lire les détails ; le texte de la fiche reste disponible indépendamment du dessin.

La PWA a servi hors ligne les trois transmissions et leurs premières fiches,
en plus des dossiers, graphes, récits, modèle et calendrier. Ses 398 ressources
épinglées sont vérifiées. La mise à jour reste explicite, une génération
incomplète conserve la précédente et l’effacement reste limité au périmètre.
Les 239 pages servent leurs octets exacts ; liens locaux et fragments résolvent.
Le modèle source et les JSON graphe/récit/questions sont identiques octet par
octet à UX02. La génération est déterministe et sa réapplication idempotente.

Voir les preuves (document historique ou livrable local non inclus),
l’index mobile (document historique ou livrable local non inclus) et le
diagramme de focus (document historique ou livrable local non inclus).

## Publication et suite

La [PR #11](https://github.com/yannickhuchard/air/pull/11) a fusionné UX02 et les
travaux précédents dans `main`, commit `cf76b3b`, avec 95 tests locaux passants.
UX03 est poussé et fusionné par la [PR #12](https://github.com/yannickhuchard/air/pull/12),
commit `0b30ab2713f7dc5483661f138e00b7790de6a8eb`, le 4 octobre 2026.
Le reçu UX03 conserve son état historique avant cette publication. Aucune CI n’a été exécutée et la distribution publique rc9 n’est
pas requalifiée par ces travaux.

UX00 reste ouvert pour le connecteur. La [suite UX04](ux04-cooperation-site-agent.md)
apporte la capsule de coopération et la reprise dans la portée locale. UX05,
séances formatives et réception du périmètre avec des participants, reste à réaliser. Aucune nouvelle recette native ChatGPT ou Claude, aucun participant
utilisateur ni certification d’accessibilité. Les trois dossiers Asteria restent
`NOT_READY` ; leurs neuf tests métier originaux restent non exécutés. Les
résultats techniques du site ne reçoivent pas ces essais métier à leur place.
