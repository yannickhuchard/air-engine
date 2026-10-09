# P08 - Pilote technique local

**Statut courant : pilote technique terminé**, dépendance P07 satisfaite et contrôle
`LOCAL_TECHNICAL_EVIDENCE_COMPLETE`, sans anomalie. Voir la
[clôture locale](cloture-p07-p08-local.md) et le contrôle courant (document historique ou livrable local non inclus).
Validation indépendante toujours différée ; G1 est désormais reçu par une
[décision séparée](g1-reception-locale.md). Les récits d'exercices ci-dessous
conservent les étapes historiques.

Le [périmètre décidé le 28 septembre](decision-p07-p08-local.md) reporte la validation
indépendante et G1. Ce lot prépare l'utilisation sur le poste d'un architecte sous
Windows, SQLite et authentification locale. Aucun serveur central n'est requis.

## Résultats du 28 septembre 2026

Le dossier actualisé (document historique ou livrable local non inclus) réunit la recette du poste
sur les sources LF, exactement identiques à celles de l'archive rc9 testée, et le
dossier P07 complet. Son contrôle (document historique ou livrable local non inclus) retourne
`LOCAL_TECHNICAL_EVIDENCE_COMPLETE` avec `issues: []`. Le
[périmètre local publié](perimetre-local-supporte.md) décrit les usages et limites
de cette candidate. **Aucun travail technique P08 ne reste ouvert dans ce périmètre.**

Les exercices locaux sont exécutés sur la candidate `0.34.0rc9`, commit `d0a4968` :
installation neuve hors ligne, réinstallation, mise à niveau depuis rc8, retour à la
sauvegarde antérieure, restauration locale et trois dossiers Asteria. Ils passent.
La restauration mesurée dure 0,430 s dans cet environnement de recette ; ce n'est pas
un objectif de temps garanti. La distribution testée est figée avant ajout des rapports.

Pour contrôler la clôture courante depuis le dépôt avec son Python :

```sh
python scripts/p08_local_reception.py docs/traceability/p08-local-current.json
```

Le contrôle recalcule les références épinglées, les critères du pilote et la
complétude P07 ; il ne se contente pas d'un statut PASS déclaré. Il termine avec
le code 0 pour le dossier courant. Sous Windows, utiliser `.venv/Scripts/python.exe` ;
sous Unix, `.venv/bin/python`.

Le dossier historique (document historique ou livrable local non inclus) et son
résultat initial (document historique ou livrable local non inclus) restent conservés :
ils donnaient `INCOMPLETE` avec `p07.incomplete` avant la clôture P07. Ils ne sont
pas la commande de réception courante et leurs résultats ne sont pas réécrits.

## Critères de clôture P08

| Critère local | État | Preuve ou livrable |
| --- | --- | --- |
| Trois dossiers Asteria, diagnostics et isolation des accès | Reçu dans le périmètre de conception | Démonstration calculée (document historique ou livrable local non inclus) |
| Installation neuve depuis le wheel, hors ligne, SQLite/local | Reçu | Distribution (document historique ou livrable local non inclus) |
| Réinstallation et mise à niveau rc8 → rc9 avec conservation des identités/révisions | Reçu | Distribution (document historique ou livrable local non inclus) |
| Sauvegarde, restauration sans source disponible, identité renouvelée et digests conservés | Reçu | Recette du poste (document historique ou livrable local non inclus) |
| Retour arrière par sauvegarde antérieure dans un nouveau home | Reçu | Distribution (document historique ou livrable local non inclus) |
| Dépendance P07 : Codex, ChatGPT et parcours transversaux | Complète techniquement | Contrôle P07 (document historique ou livrable local non inclus) |
| Périmètre supporté, limites, incidents, déploiement progressif et retour arrière | Publiés | [Périmètre local](perimetre-local-supporte.md), procédures ci-dessous |

La licence et les responsabilités nominatives non attribuées sont signalées dans
le périmètre publié. Leur attribution, la validation indépendante, le second poste
physique et G1 restent des décisions différées ; aucune signature n'est déduite
de cette clôture technique.

## Résultats de conception des trois dossiers

| Dossier fictif Asteria | Résultat calculé conservé |
| --- | --- |
| SAV et interventions | UNKNOWN |
| Atelier industriel | VIOLATED |
| Identités partagées | CONFLICTING |

Les trois portes restent bloquées conformément aux données de démonstration ; neuf
scénarios métier restent non exécutés. Les tests externes synthétiques supplémentaires
sont distingués de ces scénarios. Ce résultat montre les diagnostics AIR, sans annoncer
que les solutions modélisées sont développées ou exécutées.

## Parcours et preuves

1. Installer l'archive et le wheel dans un environnement Python neuf, depuis un
   wheelhouse local ; vérifier `health`, `doctor`, identité et révisions après
   réinstallation. `scripts/qualify_release.py` exerce également la mise à niveau
   depuis la candidate précédente et le retour à sa sauvegarde dans un nouveau home.
2. Rejouer `scripts/demo_metier.py --qualify-external-proofs` sur les trois dossiers
   Asteria. Les revues et tests signés de cette recette sont synthétiques. Conserver
   les neuf cas métier non exécutés, les trois portes bloquées et leurs raisons.
3. Rejouer `qualify_workstation.qualify_local` dans une installation jetable : accès
   anonyme refusé, lecteur sans écriture, diagnostic sans jeton, sauvegarde cohérente,
   source rendue indisponible, restauration avec mêmes digests et identité renouvelée.
4. Figer les versions et empreintes, joindre le résultat P07 au dossier. Aucun
   script ne remplace une preuve native manquante par une simulation protocolaire.

Les rapports conservent `production_ready: false`. La réussite des exercices
automatisés est une réception technique bornée, pas une signature humaine G1.
Les durées d'automatisation ne sont pas des temps de prise en main d'un utilisateur.

## Mise en service progressive

Avant le premier dossier réel, le propriétaire du poste vérifie le profil qualifié,
les limites publiées dans `docs/etat-implementation.md`, puis suit le SKILL
`air-install`. Il crée une identité nominative par client, limite ses namespaces,
et vérifie `whoami`. Un tunnel partagé conserve une identité de connexion commune :
il ne devient pas une authentification individuelle par utilisateur ChatGPT.

Commencer par un dossier non sensible, vérifier les références et hypothèses avec
l'architecte, puis exporter les livrables destinés aux équipes de réalisation.
Étendre ensuite aux trois domaines du pilote ; préserver la distinction entre
objets déclarés, résultats calculés, validations de conception et exécution métier.
Faire une sauvegarde avant changement de version et avant toute extension du pilote.
Revenir en arrière par restauration dans un nouveau home avec l'ancienne distribution,
jamais par rétrogradation directe de la base courante.

## Exploitation et support

- Le propriétaire de chaque poste conserve les sauvegardes hors du dossier de travail,
  choisit leur emplacement protégé et vérifie périodiquement une restauration.
- Aucune purge automatique de l'audit n'est activée. La perte possible correspond au
  travail depuis la dernière sauvegarde réussie ; aucune durée de rétention entreprise
  ou garantie de disponibilité n'est promise par défaut.
- En incident : relever version, code AIR, résultat `doctor`/`monitor` et étapes de
  reproduction. Ne jamais envoyer identifiants, base ou journaux bruts dans un ticket.
  Pour une faille, suivre `SECURITY.md`. Conserver la sauvegarde avant correction.
- Après mise à jour : vérifier la compatibilité de la distribution et redémarrer le
  processus MCP du client. Pour ChatGPT, vérifier d'abord le serveur local et le
  runtime du tunnel, puis rafraîchir le catalogue de l'application.

La licence reste **non attribuée** (`NOT_ASSIGNED` dans le manifeste de distribution).
Ce lot n'accorde aucun nouveau droit de redistribution et n'invente pas une licence.
Les responsables nominatifs de support, conservation, risques et décision G1 restent
à désigner avant réception organisationnelle. L'équipe indépendante, le second poste
physique et la revue sécurité indépendante sont différés explicitement, pas réussis.
