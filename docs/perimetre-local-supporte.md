# Périmètre local livré et qualifié

État publié le 28 septembre 2026 pour **AIR 0.34.0rc9**. Cette page décrit le
périmètre vérifié et ses limites. **P07 et le pilote technique P08 sont terminés**
dans le périmètre local ; la validation indépendante reste différée.
**G1 est désormais reçu dans ce périmètre**, avec licence Apache-2.0 et
[décision explicite](g1-reception-locale.md).
La branche de développement 0.35.0.dev1 ne bénéficie pas de cette qualification rc9. La candidate
n'est pas une version LTS et aucun engagement de support contractuel n'est annoncé.

## Installation retenue

| Élément | Périmètre vérifié |
| --- | --- |
| Poste | Windows 11, compte local de l'architecte, volume avec ACL persistantes |
| Python | Python 3.12.14 dans les derniers exercices P08 ; minimum logiciel 3.11 |
| Données | SQLite dans un home AIR privé, révisions immuables et audit |
| Identité | Authentification locale ; un fichier protégé par identité |
| API | Boucle locale ; aucun serveur central nécessaire |
| Installation | Python seul, archive et wheel, dépendances épinglées ; aucun Docker, Node, cloud ou IdP obligatoire |
| Hors ligne | Installation testée depuis un wheelhouse préparé ; l'accès à un agent cloud nécessite sa connexion |
| Cycle de vie | Réinstallation, mise à niveau rc8 → rc9, sauvegarde, restauration dans un nouveau home, retour arrière |

La distribution effectivement testée est celle du commit `d0a4968`, avec les
empreintes de l'archive, du wheel et des dépendances (document historique ou livrable local non inclus).
Les rapports ajoutés ensuite au dépôt ne font pas rétroactivement partie de cette archive.
Cette réception Windows ne qualifie pas automatiquement macOS, Linux ou une autre
combinaison de versions, même si le code prévoit ces plateformes.

## Travail de l'architecte

AIR permet de conserver le contexte, les sources, les modèles et leurs révisions ;
préparer des variantes et changements ; vérifier références, contrats et portes ;
effectuer les calculs et simulations des profils implémentés ; produire les dossiers
destinés aux équipes de réalisation. Les capacités exactes et les contrôles non
exécutés sont exposés par `air_capabilities` et les rapports du moteur.

Les résultats distinguent hypothèses déclarées, diagnostics calculés, avis de conception
et preuves externes qualifiées. `UNKNOWN`, `CONFLICTING`, `VIOLATED` ou une porte bloquée
sont des résultats possibles. La conformité complète au white paper n'est pas annoncée.
Les modèles ne constituent pas des applications métier déjà développées ou exécutées.

La démonstration Asteria couvre SAV/interventions, maintenance d'atelier et gestion des
arrivées/mobilités/départs. Les trois parcours de conception passent leur recette ; les
diagnostics et neuf scénarios métier non exécutés restent visibles dans le
rapport calculé (document historique ou livrable local non inclus).

## Clients et collaboration

- **CLI/API/MCP AIR** : adaptateurs du même noyau et contrôles d'autorité serveur.
- **Codex** : recettes natives observées de découverte, lecture, proposition, idempotence,
  reprise, refus hors mandat, annulation et récupération après interruption. Les versions
  et limites de chaque recette restent dans les preuves P07.
- **ChatGPT** : connexion native par tunnel, contexte, proposition sourcée et idempotente,
  référence invalide, lecture hostile, refus d'accès et récupération observés dans le
  banc isolé. La reprise Codex ↔ ChatGPT et la parité des diagnostics sont vérifiées.
  Les refus d'admission et d'activation, l'annulation et le nouveau calcul passent.
  Voir les preuves complètes (document historique ou livrable local non inclus).
  La qualification cumule les versions clientes indiquées par cas ; elle ne prétend
  pas que tous les cas ont été rejoués sur la dernière version cliente.
- **Claude** : intégration conservée, retirée des clients requis P07. Les autres familles
  ne sont pas déclarées qualifiées par analogie.

Une connexion de tunnel utilise l'identité de son fichier AIR ; elle ne constitue pas
un SSO individuel des utilisateurs ChatGPT. Le profil contributeur masque les outils
d'engagement et les droits sont revérifiés à chaque appel. Chaque poste conserve sa
base autonome ; aucune synchronisation automatique ou fédération reçue n'est promise.

## Installer, exploiter et revenir en arrière

L'IDE commence par [le skill d'installation](../.agents/skills/air-install/SKILL.md),
puis [le guide d'installation](installation.md). Après installation : `doctor`,
`workstation-check` et vérification de l'identité et des namespaces accessibles.
Commencer par un dossier non sensible, puis élargir après vérification des livrables.

Suivre les [procédures du poste](lot-poste-local.md) : sauvegarde avant mise à niveau,
copie protégée sur un support indépendant, restauration dans un nouveau home et nouvelles
identités. Les données créées après la dernière sauvegarde réussie ne sont pas récupérées
par cette sauvegarde. Aucun ordonnanceur de sauvegarde, RPO automatique ou SLA n'est livré.
La conservation reste sous la responsabilité du propriétaire du poste ; aucune purge
automatique de l'audit n'est activée.

Pour un incident, fournir version, code AIR et reproduction expurgée. Suivre
[SECURITY.md](../SECURITY.md) pour une vulnérabilité ; ne pas publier la base, les jetons
ou les journaux privés. Licence, contacts nominatifs et engagements de support restent
à fixer par le propriétaire du projet. Le manifeste porte `NOT_ASSIGNED` pour la licence.

## Étapes suivantes

La [clôture technique locale P07/P08](cloture-p07-p08-local.md) comprend les vingt cas
natifs requis, les six parcours transversaux et les exercices du pilote local.
Le contrôle P08 (document historique ou livrable local non inclus) ne présente plus d'anomalie.
Les validations indépendantes et G1 restent différées selon la décision de périmètre.
PostgreSQL/OIDC étendus et serveur central relèvent de P09 ; la complétude normative
reste dans P10–P14. Aucune CI n'est déclenchée pendant ces travaux.
