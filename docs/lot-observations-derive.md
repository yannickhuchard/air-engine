# Observations, dérive et incidents - tranche 12

Version 0.12.0.dev1 ; 236 tests réussis sur SQLite et PostgreSQL 18.6. Recettes runtime, M1 et cycle d’engagement PASS_SCOPED. White paper §16 et A.12, page 52 ; L01/L02/L15.

Introduire un sous-profil explicite pour RuntimeObservation, Drift et Incident, en préservant leurs champs normatifs et les règles de référence. Les premiers sujets observés sont des Scope ou objets déjà supportés. RuntimeInstance, environnements et artefacts de déploiement viendront avec leurs propres schémas ; aucun type générique ne doit masquer leur absence.

## Observations

Chaque observation épingle son sujet, son signal, sa fenêtre, sa valeur typée et la couverture déclarée. La provenance permet de localiser la source. Le record ScopeCoverage, seulement nommé dans le white paper, demande une ADR : périmètre, références incluses/exclues et limites. Une observation partielle ne devient pas une couverture d’entreprise complète. Les données restent DRAFT tant que leur qualification n’est pas réceptionnée.

L’import manuel ou par fichier produit des objets et un reçu d’ingestion authentifié. Il ne contacte aucun système distant. La source et le sujet conservent leurs identités et révisions ; la répétition d’un même contenu est idempotente.

## Comparaison

Comparer des observations exactes à une attente explicitement modélisée, avec AIR-Expr borné pour les comparaisons exécutables. Ne pas transformer automatiquement une exigence en texte libre en prédicat. Conserver UNKNOWN et CONFLICTING, couverture, fenêtre et limites. Une dérive observée ne modifie pas le modèle attendu et ne déclenche aucune remédiation automatique.

Les incidents peuvent regrouper observations et scope, avec fenêtre, description et liens d’apprentissage. Une résolution déclarée reste distincte d’une vérification d’efficacité. Les changements de modèle sont proposés via les mêmes services immuables.

## Recette

Trois dossiers Asteria : réponse ERP indisponible, mesure atelier hors attente, état IAM contradictoire. Vérifier l’ingestion, les accès transverses, les fenêtres, les valeurs typées, les comparaisons effectivement calculées, les inconnues et la conservation des anciennes baselines. Qualifier SQLite et PostgreSQL, migrations éventuelles, transfert et reprise par CLI/HTTP/MCP.

## Binding exécutable

Le catalogue passe à 20 types persistables avec RuntimeObservation, Drift et Incident. Le nouveau profil air.runtime/0.12 contient 18 types de données plus Baseline et ChangeSet ; les profils historiques conservent leurs propres types autorisés. ScopeCoverage est défini dans ADR 0029, comme choix explicite de sous-profil.

observation-ingest accepte une Source exacte et jusqu’à 128 RuntimeObservation. Source, sujets et références doivent être lisibles, les namespaces d’observation modifiables ; le reçu conserve l’auteur authentifié. Les fenêtres de collecte et dates de capture futures sont refusées. La transaction contient observations, reçu et audit, avec idempotence de clé et rollback sur conflit.

runtime-compare accepte scope et attente exacts, une fenêtre, une date de lecture historique as_of, une fraîcheur maximale et un mapping AIR-Expr explicite. Chaque entrée du prédicat Boolean doit être liée et effectivement référencée. Sources périmées, fenêtres non couvertes et artefacts non interprétés deviennent UNKNOWN. Les erreurs de types ne deviennent pas une réussite. La comparaison est bornée à 1 MiB de contexte et de rapport.

Les outils MCP sont air_runtime_ingest et air_runtime_compare. Les types persistables utilisent les services put/bundle-put, baseline-create, change-propose et baseline-export existants. La comparaison ne crée pas automatiquement une Drift ; le rédacteur propose explicitement l’écart et son impact. Un traitement Contribution/Decision ne peut pas encore fermer une baseline, ces types restant indisponibles.

## Démonstration exécutée

scripts/demo_runtime.py rejoue les trois dossiers dans une même installation SQLite isolée : confirmation ERP indisponible, mesure de 540 secondes comparée à un seuil déclaré de 300, statut IAM contradictoire. Les résultats sont VIOLATED, VIOLATED et CONFLICTING. Une règle de fraîcheur plus stricte produit UNKNOWN pour les trois cas.

Chaque dossier reçoit une baseline runtime fermée de 28 objets. Les baselines de conception restent conservées ; restauration et replay CLI/HTTP/MCP sont vérifiés. Les sources et mesures sont fictives, avec dates historiques cohérentes, et la qualification reste DRAFT. Rapport : tmp/demo-asteria/runtime.json ; vue : runtime.html.

Le contrôle de source future s’applique aussi aux nouvelles offres de capacité et aux nouvelles admissions/activations. Les fixtures capacitaires utilisent désormais une source de déclaration distincte du brief d’entreprise daté du lendemain. Les reçus historiques sont conservés ; ce contrôle ne libère aucun travail engagé.
