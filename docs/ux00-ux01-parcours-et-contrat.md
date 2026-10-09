# UX00 et UX01 : contrat client et parcours du Projet d’architecture

Incrément du 3 octobre 2026, branche `0.35.0.dev1`, à la suite de
l’[audit UX](audit-ux-projet-architecture-2026-10-03.md).

## UX01 livré dans la portée locale

Chaque dossier généré fournit désormais six pages de lecture : COMEX, managers
métier, DSI, architecture entreprise, architecture solution et équipes de
réalisation. La vue d’ensemble permet de choisir son parcours. Le catalogue des
37 sujets reste accessible, avec tous les diagrammes et leurs pages dédiées.
Les groupes de navigation sont repliés hors du sujet courant, y compris sans
JavaScript ; la navigation mobile conserve son menu compact.

Une question mène au sujet détaillé, à ses diagrammes et à ses objets sources
exacts. Les déclarations narratives disponibles sont citées directement, avec
un aperçu limité à deux extraits de 500 caractères. Les objets complets restent
accessibles. La recherche locale couvre les questions et leurs sources ; elle
ne constitue pas encore une recherche transversale entre tous les dossiers.

Les états distinguent sources présentes, sujet non documenté, sujet partiel et
contrôle calculé. Les coûts, jalons, RACI, organisation, exigences de qualité et
estimations signalent leurs dimensions absentes. Une estimation de charge ne
devient pas un budget CAPEX/OPEX ; une responsabilité n’est pas attribuée au
lecteur. La présence d’objets ne démontre pas la complétude de leurs engagements.

Les critères de préparation présentent leur sens et leurs actions. L’absence
de contrôle ou d’exigence de qualité applicable n’est plus traduite par « rien
à construire ». Les tables vides et la racine d’organisation absente utilisent
des libellés lisibles, sans `None` ni `_Aucun élément._`.

`questions.json` conserve la baseline `{id, revision, digest}`, les empreintes
des objets sources et celle de la projection. Il n’accorde aucun droit et
n’altère pas les exports immuables. Les parcours ne sont pas des contrôles
d’accès : le destinataire autorisé reçoit toujours le site complet.

## UX00 : outillage livré, réception du connecteur ouverte

Le [contrat client courant](contrat-client-agent.md) donne la procédure commune.
`air_capabilities.client_contract` expose les empreintes des schémas par profil.
`air client-contract-check` compare un catalogue réellement observé et,
facultativement, le contexte exact attendu et lu. Il ne modifie aucun réglage
et ne transforme pas une observation fournie en recette d’un client natif.

Le plugin connecté dans Codex lit l’identité et le nouveau contrat. Sa lecture
avec l’URN issue d’un reçu P07 reste rejetée par le schéma du connecteur avant
AIR. Le catalogue visible ne publie toujours pas le nouvel outil de branding.
La cause exacte du rejet, cache ancien ou restriction du connecteur, reste à
confirmer. Aucun identifiant de substitution ni contournement n’a été utilisé.
Ce banc P07 est distinct du registre des trois dossiers Asteria du site.

**UX00 n’est pas clos** : les trois lectures exactes demandées par le critère
de réception dans le plugin ne sont pas reçues. La recette native ChatGPT des
nouveautés reste à faire. La documentation et la source du skill du plugin décrivent
la récupération, sans modifier les qualifications historiques rc9/P07.

## Vérification et démonstration

La preuve de l’incrément (document historique ou livrable local non inclus) conserve les
tests locaux, les contrôles au navigateur et les trois dossiers fictifs.
Le reçu du plugin (document historique ou livrable local non inclus) est expurgé des
jetons, chemins privés et métadonnées d’erreur de la plateforme.

La démonstration locale comporte 206 pages HTML et 48 diagrammes. Les 72
parcours au navigateur couvrent les six publics, les trois dossiers et quatre
largeurs : 320, 390, 768 et 1440 pixels. La recherche, la navigation clavier
vers un sujet et le contexte exact passent. Tous les liens et fragments
statiques résolvent ; les 206 réponses HTTP correspondent aux fichiers épinglés.
Les trois pages COMEX ont aussi été relues hors ligne dans un navigateur isolé.
Le modèle JSON est identique octet par octet à celui de l’incrément précédent.

| Dossier fictif | Parcours de lecture | Observation reçue |
| --- | --- | --- |
| [Portail SAV](http://127.0.0.1:8741/dossiers/n88bb2217e4d6/role-comex.html) | COMEX, besoin et préparation | Déclarations sourcées accessibles ; absence de postes CAPEX/OPEX signalée |
| [Maintenance d’atelier](http://127.0.0.1:8741/dossiers/n021b46b2d71b/role-dsi.html) | DSI, réalisation et exploitation | Accès au sujet dédié au clavier ; exigences de qualité absentes signalées |
| [Identités et accès](http://127.0.0.1:8741/dossiers/naa10599f1cc0/role-solution.html) | Architecture solution, composants et preuves | Liens vers le modèle et ses sources exactes ; statut de préparation incomplet conservé |

Ces liens désignent la prévisualisation locale courante. Pour une autre
installation, régénérer le site avec les commandes ci-dessous. Les captures
grand écran (document historique ou livrable local non inclus) et
mobile (document historique ou livrable local non inclus) documentent les vues inspectées.

Les parcours SAV, maintenance et identités sont des designs déclarés pour leur
réalisation ultérieure. Ils gardent `NOT_READY`, leurs blocages et les neuf
tests métier originaux non exécutés. Le succès du site ne reçoit ni leur
architecture métier ni la future application.

Pour reproduire sur un nouveau répertoire :

```powershell
.venv/Scripts/python.exe scripts/demo_architecture_site.py --output tmp/ux-reading-demo
.venv/Scripts/python.exe -m air.site_server tmp/ux-reading-demo/project/livrables/site --port 8741
```

`scripts/qualify_site_questions.cjs` est un contrôle optionnel de développement
avec Node, Playwright et un navigateur isolé. AIR reste installable avec Python
seul. Il vérifie les six publics, les questions, le clavier et quatre tailles
d’écran ; un argument final désignant le serveur de prévisualisation local
permet aussi de vérifier les nouvelles pages hors ligne dans une copie isolée.

Il n’y a eu aucune séance avec participants ni certification d’accessibilité.
UX02 reste à réaliser pour le design visuel et les animations de lecture du
graphe ; UX03 pour la transmission à la réalisation ; UX04 pour le passage
structuré site/agent ; UX05 pour la recherche utilisateur et la qualification.
