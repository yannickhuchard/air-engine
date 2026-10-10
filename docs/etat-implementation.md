# État de réalisation public

## Lot A reçu dans le périmètre local - 10 octobre 2026

La [consolidation locale](lot-a-consolidation.md) comprend la régression
publique complète (1 176 succès, un skip privé, aucun échec), les retouches
finales vérifiées, trois dossiers Asteria, les builds reproductibles et les
recettes du paquet : installation neuve hors ligne, réinstallation, mise à
niveau rc9 et restauration. Codex 0.159.2 et ChatGPT exécutent réellement les
parcours de lecture, diagnostic, proposition, reprise et compilation.

La [barre de complétude](ux-barre-completude.md) ouvre huit parties depuis
l’accueil du dossier : pourcentage documentaire, manques, contrôles restants,
travail déclaré et liens vers les sujets exacts. Elle fonctionne au clavier
et sans JS. Les 24 vues Asteria et la PWA sont reçues localement.

La version reste 0.35.0.dev1. Cette réception ne vaut ni conformité normative
totale, ni compatibilité avec tous les clients, ni revue indépendante, ni
serveur centralisé ou admission dans un annuaire. Aucune CI lancée.
Voir le [reçu structuré](traceability/lot-a-2026-10-10.json).

## Sources publiques 0.35.0.dev1

La branche principale publie les sources de développement du 9 octobre 2026
sous Apache-2.0. La release 0.34.0rc9 reste disponible et inchangée sur son tag.
Ce snapshot ne constitue pas une réception globale de production.

Le moteur, SQLite et l’authentification locale restent accessibles avec Python
seul. PostgreSQL et OIDC sont des options indépendantes. Le profil initial est
le poste autonome de l’architecte ; aucune fédération entre installations n’est
déduite du travail en portefeuille sur une même instance.

Les sources incluent le site Projet d’architecture responsive/PWA, les diagrammes
BPMN descriptifs, les cartes de parcours interactives, le branding, le détail
financier et son Sankey, le Management Summary, le pilotage de transformation,
les News et la préparation de vidéos par CLI/MCP. Le rendu MP4 local est optionnel
et exige Node/npx, Chromium, Hyperframes et FFmpeg ; ces outils ne sont pas des
dépendances de l’installation du moteur. Les modèles décrivent les futurs
systèmes ; ils ne les exécutent pas.

Les trois dossiers Asteria sont fictifs. UNKNOWN, VIOLATED, CONFLICTING et les
tests métier NOT_EXECUTED restent visibles. Aucune mesure de robots, revue
indépendante, validation juridique ou qualification native d’un nouveau client
n’est fabriquée. Les dossiers privés, documents importés et l’historique privé
ne sont pas inclus dans cette distribution.

Consulter la [validation du snapshot](validation.md), les
[exemples Asteria](../fixtures/enterprise/asteria/README.md), les
[formats de diagrammes](diagrammes-processus-et-experience.md), le
[pilotage](synthese-et-pilotage-transformation.md) et
[l’actualisation News/vidéos](actualiser-news-videos.md).
Les tests locaux de cette publication ne valent ni CI, ni recette sur un second
poste physique, ni réception des autres OS ou d’un annuaire de plugins.
