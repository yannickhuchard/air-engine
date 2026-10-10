# État de réalisation public

## Lot C : paquets et réception des constructeurs - 11 octobre 2026

Les distributions [moteur 0.35.0.dev3](https://github.com/yannickhuchard/air-engine/releases/tag/v0.35.0.dev3)
et [plugin 0.1.10](https://github.com/yannickhuchard/air-plugin/releases/tag/v0.1.10)
sont publiées après fusion. Les huit assets sont téléchargés sans authentification
et comparés aux fichiers reçus. Le wheel final passe installation hors ligne,
réinstallation, mise à niveau depuis dev2, restauration et retour à la sauvegarde.
Il rejoue les 13 commandes CLI, les quatre rôles et la lecture MCP, puis huit vues
navigateur avec et sans JavaScript. Douze tests finaux vérifient les limites
de transport et la transmission. Voir le [reçu de publication](traceability/lot-c-publication-2026-10-11.json).
Ces préversions ne revendiquent pas une qualification globale de production.

La version 0.35.0.dev3 livre les [paquets de construction](lot-c-transmission-equipes.md).
Une version fige la baseline, les unités, contrats, critères, cas et responsabilités.
Les identités mandatées reçoivent chaque rôle R et A ou ouvrent des questions.
Le droit receive et les builder_roles exacts sont contrôlés par le serveur ;
expiration, retrait et politique modifiée rendent les réceptions inactives.
Une nouvelle version exige des réceptions nouvelles, sans masquer les unités exclues.

Six commandes CLI et outils MCP partagent ces services. La page « Préparer la
réalisation » présente les versions, responsables, questions, réceptions et unités
sans paquet. La synthèse reste datée par son export, sans autorisation de lancement.
Les adaptateurs IDE n'activent pas automatiquement les outils engageants.

Recette technique locale : 88 tests, puis 22 contrôles finaux ; deux équipes
fictives, quatre rôles, 13 commandes CLI et lecture MCP identique. Huit vues
navigateur passent à 320/390/768/1440 px, avec et sans JavaScript, détails au clavier
et liens lisibles. Les trois parcours Asteria DEMO-METIER-1 passent : SAV,
maintenance et identités. Voir le [reçu technique](traceability/lot-c-2026-10-11.json).
Les données fictives ne prouvent ni avis humain, ni tests de réalisation exécutés,
ni autorisation de déployer. Les artefacts externes ne sont pas copiés dans le paquet.
Plugin source 0.1.10 ; publication GitHub et décision OpenAI restent distinctes.

## Lot B : complétude contextuelle et contrats - 10 octobre 2026

La version 0.35.0.dev2 livre les [profils et contrats](lot-b-profils-et-contrats.md).
Cinq contextes explicites posent les questions absentes du dossier. Les exclusions
restent ouvertes sans acceptation effective de la baseline exacte et se rouvrent
après révocation ou rejet. InterfaceSpecification couvre schémas locaux exacts,
préconditions/postconditions/invariants purs, politiques et exemples ;
DataLifecycleSpecification décrit clés, indexes, rétention et plans de migration.
Le profil air.build-design/0.35 ajoute un treizième critère. Les anciens profils
conservent leurs douze critères sans migration implicite.

CLI, API, MCP, guide et skills exposent les mêmes services. L’accueil ouvre la page
de complétude avec sources et suites téléchargeables. Deux prototypes indépendants
réalisent 106 échanges HTTP locaux : 101 valides, quatre entrées refusées et un
conflit de clé ; le rejeu et un prix incorrect sont vérifiés. La suite portable
est exécutée par le CLI. La présence documentaire et les exemples de design ne
prouvent pas la sécurité, concurrence, délais, effets métier ou compatibilité
entre versions du système futur.

Régression locale de 190 tests, puis 60 tests ciblés après correction des budgets
des dossiers volumineux. Trois dossiers Asteria passent DEMO-METIER-1 ; les sites,
barres et PWA sont rejoués. Codex 0.159.2 appelle les trois outils en lecture seule
sur la fixture, avec configuration MCP propre à cette invocation. Cela ne qualifie
pas la redécouverte automatique de tous les clients ni leur marketplace.

Plugin source 0.1.9. Aucune CI ni nouvelle admission en marketplace. Voir le [reçu](traceability/lot-b-2026-10-10.json) et la [roadmap](ROADMAP_REFERENCE.md).


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
