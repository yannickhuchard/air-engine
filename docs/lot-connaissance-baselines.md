# Tranche 02 - Connaissance, baselines et propositions

Version livrée : **0.2.0.dev1**. Profil expérimental : **air.foundation/0.2**.
Cette tranche contribue à L01, L02, L03 et L06 ; elle ne réceptionne pas ces lots
dans leur intégralité et ne revendique pas la conformité complète AIR 0.1.

## Résultat

Un architecte peut importer un graphe de brouillons, vérifier ses références,
figer une baseline, l’exporter et proposer une nouvelle version sans modifier
l’ancienne. Les opérations passent par les mêmes services depuis la CLI et HTTP.
SQLite reste le backend par défaut ; aucune dépendance n’a été ajoutée.

| Fonction | Garantie vérifiée |
| --- | --- |
| Import de brouillons | Import atomique ; un conflit annule l’ensemble de l’import ; les références peuvent rester ouvertes jusqu’à la création de baseline |
| Références | Révision exacte, type cible selon le champ, une révision par identité dans une baseline ; un objet présent ailleurs dans la base ne ferme pas une référence absente de la baseline |
| Connaissance | Assertion, Evidence, Assumption et Unknown, en plus de Scope et Source ; liens de preuve orientés et réciproques ; inconnues bloquantes conservées |
| Baseline | Manifeste trié, références avec type/digest, lockfile dérivable adressé par contenu, parents exacts, immutabilité et répétition idempotente |
| ChangeSet | ADD/REPLACE/REMOVE sur des révisions exactes, vecteur attendu contrôlé, proposition et baseline cible dans une transaction ; refus d’une approbation fournie par le client |
| Rejeu | Export des membres et du lockfile, vérification des digests, reconstruction d’une baseline racine dans une base SQLite neuve |

Une baseline fermée peut contenir une inconnue bloquante : elle capture alors
fidèlement un dossier incomplet. Elle n’accorde aucun droit de décision, publication,
engagement ou lancement. Le rapport indique toujours decision_ready=false dans
cette tranche ; les services de qualification et d’autorité restent à construire.

## Conventions du profil

Les six types de données acceptés sont air.Scope, air.Source, air.Assertion,
air.Evidence, air.Assumption et air.Unknown. air.Baseline et air.ChangeSet sont
deux types techniques supplémentaires, créés exclusivement par leurs services.
Les écrire directement avec put ou bundle-put est refusé.

Les références de modèle contiennent id et revision. Leur type attendu provient
du registre de champs, par exemple Evidence.source → Source et
Assertion.subject_scope → Scope. Les cycles Evidence ↔ Assertion sont légitimes.
Les URI owner, recorded_by et resolution_owner relèvent de l’identité externe ;
elles ne sont pas des références à des objets AIR du graphe.

Evidence.supports_or_refutes contient id, revision et direction SUPPORTS/REFUTES.
L’assertion doit référencer la même preuve. Une assertion SUPPORTED exige un lien
SUPPORTS ; REFUTED exige REFUTES ; des preuves dans les deux sens exigent CONTESTED.
La qualité réelle de la source et la vérité du propos ne sont pas déduites de ces
liens. ESTABLISHED est refusé tant que la revue authentifiée n’est pas implémentée.

Une Assumption reste OPEN ou UNDER_TEST avec responsable dans meta.owner, impact,
plan de vérification et échéance. Unknown distingue OPEN, INVESTIGATING et RESOLVED ;
la résolution exige une référence exacte vers Assertion ou Evidence. BLOCK et
INFORMATIONAL sont les politiques provisoires du profil. La clôture sémantique
d’une inconnue reste une responsabilité humaine ; un pointeur ne la prouve pas.

Le corps Baseline contient members, dependency_lock, profiles et parent_baselines.
Chaque membre inclut id, revision, type et digest. dependency_lock désigne le JSON
canonique des membres et du profil, reconstruit à l’identique lors de l’export.
Aucun téléchargement ou accès à un locator de Source n’est effectué par le moteur.

Les opérations ChangeSet sont des changements au niveau de l’objet entier, avec
before/after résolus. REPLACE conserve identité/type et avance la révision. Une
opération par identité est permise ; les opérations restent une séquence ordonnée.
Le vecteur expected_revisions doit correspondre à tous les membres de la base.
Le service derive l’identité de la baseline proposée du digest du ChangeSet : une
répétition ne peut pas produire une nouvelle cible arbitraire. Les propositions
peuvent former des branches ; aucune tête de branche mutable ni fusion automatique
n’est introduite. Le diff retourné est structurel, au niveau des objets ; l’analyse
d’impact et le diff sémantique de champs restent à réaliser.

## Contrôle normatif exécuté

AIR-V003 vérifie que toutes les références déclarées par le profil des six types
sont présentes à une révision exacte dans la baseline. Son résultat est SATISFIED
ou VIOLATED. Si les schémas d’entrée empêchent le contrôle, l’exécution est
NOT_EXECUTED avec résultat UNKNOWN. Une erreur de type cible reste un diagnostic
distinct et empêche également la création de baseline.

Le contrôle est **implémenté dans ce périmètre**, pas pour les 143 types du paper.
Les 83 autres règles restent affichées comme non exécutées par la validation de
graphe. La validation simple de brouillon reste une validation de schéma et conserve
les 84 règles dans sa couverture non exécutée. Voir [ADR-20](adr/0020-profils-fondation-et-fermeture.md).

## Parcours exécutable sur le dossier SAV

Depuis une installation démarrée, sur Windows :

```bat
scripts\air.cmd validate fixtures\enterprise\asteria\dossiers\sav\foundation.json --closed
scripts\air.cmd bundle-put fixtures\enterprise\asteria\dossiers\sav\foundation.json
scripts\air.cmd baseline-create fixtures\enterprise\asteria\dossiers\sav\baseline-request.json
scripts\air.cmd baseline-export urn:asteria:baseline:d01 1
```

Sur Unix, remplacer scripts\air.cmd par .venv/bin/air. Les commandes HTTP acceptent
--port et --credential. Pour proposer une modification : enregistrer d’abord les
nouvelles révisions, préparer un objet ChangeSet puis utiliser
`air change-propose change.json`. Un exemple complet est construit et exécuté par
scripts/demo_foundation.py. Une référence absente doit être ajoutée explicitement
au jeu de membres ; le service ne choisit jamais silencieusement sa dernière version.

| HTTP | Entrée ou résultat |
| --- | --- |
| POST /v1/draft-bundles | Liste de brouillons ; transaction atomique |
| POST /v1/foundation/validations | Objet ou liste ; schémas, graphe, rapport de couverture et AIR-V003 |
| POST /v1/baselines | meta de Baseline, profile, members exacts, parent_baselines ; manifeste calculé par le serveur |
| GET /v1/baselines/{id}/revisions/{n}/export | Baseline, membres, lockfile, digests et validation |
| POST /v1/changes | Objet ChangeSet ; reçu, nouvelle baseline fermée, diff et approved=false |

reader peut valider et exporter ; editor/admin peuvent importer, figer et proposer.
Les droits par objet/aspect restent à implémenter. L’API demeure sur l’interface locale.

## Vérification Asteria et limites

```bat
.venv\Scripts\python.exe scripts\demo_foundation.py
```

Ce parcours technique utilise deux bases SQLite temporaires isolées. Dans chacun
des trois dossiers : importer neuf membres, figer, exporter, restaurer à digest
identique, réviser une hypothèse, proposer, rejouer la proposition, vérifier la
baseline initiale et refuser une référence manquante. Il conserve les inconnues
bloquantes ; il n’exécute aucune action externe. Le rapport est écrit dans
tmp/demo-asteria/foundation.json.

M1-BASELINE est démontré sur les six types supportés. M1-KNOWLEDGE et M1-CHANGE
progressent, mais les contrats, droits fins, revues, impacts et vues métier manquent
encore pour réceptionner DEMO-METIER-1. La [démonstration métier](demonstration-trois-dossiers.md)
reste NOT_READY.

L’export n’est pas une sauvegarde complète de l’instance : il ne contient pas les
jetons, l’audit d’origine ni les ancêtres de la baseline. Restaurer une baseline
avec parents exige de restaurer d’abord les ancêtres ; les opérations de reconstruction
créent leur propre audit. Le test de cette tranche prouve la reconstruction du
contenu de baselines racines, pas la continuité d’un registre d’engagements.

Le schéma SQL reste en version 1 : les types supplémentaires utilisent les tables
existantes, sans migration ni réécriture des anciennes révisions. Arrêter le serveur,
relancer l’installateur puis le redémarrer charge la nouvelle version. Les options
PostgreSQL/OIDC et leurs limites de qualification restent inchangées.
