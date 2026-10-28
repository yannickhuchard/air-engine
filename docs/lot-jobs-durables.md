# Jobs de calcul durables - contrat de développement

Depuis la candidate 0.34.0rc6, le worker supervise un processus enfant par calcul avec limites OS
CPU/mémoire et durée totale ; le parent conserve le commit sous lease et autorité courantes.
Les quotas d'admission et leurs exemptions de terminaison sont décrits dans
[P06 - ressources et réception](lot-exploitation-reception.md). Les sections historiques ci-dessous
décrivent le contrat initial ; le calcul n'occupe plus directement le processus serveur.

L04.4 et L09.2 : exécuter les calculs longs sans lier leur durée à une requête IDE. Le premier worker accepte seulement plan, simulate et reconcile, déjà bornés et sans effets métier externes. Aucun script, commande, URL de callback ou admission n’est accepté.

La requête est immuable et liée à l’acteur authentifié, au jeton local par identifiant ou à la durée de validité du JWT OIDC vérifié. Aucun secret n’est conservé dans le job. Les droits sur les références sont vérifiés à la soumission, à l’exécution et à la lecture du résultat. La révocation du jeton local d’origine ou le changement du mapping OIDC bloque l’exécution différée. Un transfert de registre révoquant les jetons ne relance pas leurs jobs.

Une projection SQL job_state sélectionne les travaux prêts. Les demandes, claims, résultats et annulations conservent des reçus et audits immuables. Claim avec bail et génération, résultat sous contrôle du claim courant, trois tentatives au maximum. Une panne après calcul peut recalculer une fonction pure ; elle ne duplique pas un résultat terminal. Une panne après commit se récupère par lecture du résultat déjà enregistré.

L’annulation empêche la publication du résultat, y compris si le calcul en cours termine ensuite. Le moteur conserve les budgets internes des calculs. Le binding initial ne promet pas une interruption matérielle instantanée de Python. Une annulation ne déclenche aucune compensation métier puisque ces jobs n’exercent aucun effet externe.

Le worker s’exécute dans le processus du serveur pour le mode initial sans dépendance supplémentaire. Une commande worker permet aussi une exécution explicite. Le bail permet la reprise après arrêt brutal. SQLite conserve un seul écrivain ; PostgreSQL utilise les mêmes invariants transactionnels.

Réception : double soumission concurrente, panne après claim, bail expiré, ancien worker en retard, annulation, révocation avant exécution, refus de lecture après changement de politique, résultat métier VIOLATED dans un job SUCCEEDED, reprise après redémarrage et absence de secret dans les reçus.

## Binding livré en 0.9

job-submit reçoit idempotency_key, operation (plan/simulate/reconcile) et arguments conformes au schéma de cette opération. job-read et job-cancel reçoivent job (id/digest). API : POST /v1/jobs, /v1/jobs/read et /v1/jobs/cancel. MCP : air_submit_job, air_get_job, air_cancel_job. Seul le demandeur peut consulter ou annuler son job. Le statut terminal SUCCEEDED signifie que le calcul a terminé, même si son résultat est VIOLATED ou CONFLICTING.

Le worker démarre avec le serveur. --no-worker le désactive au lancement ; worker-once traite explicitement un job prêt. Le bail dure 60 secondes, avec au plus trois tentatives. Entrée et résultat sont limités à 1 MiB. Une nouvelle soumission avec la même clé retrouve le job précédent ; après échec terminal, utiliser une nouvelle clé pour une nouvelle autorisation.

Le schéma SQL 3 ajoute seulement job_state et son index. La migration 1/2→3 conserve les anciennes tables et reçus. Les sauvegardes SQLite 1/2/3 et les transferts de registre 2/3 sont lisibles. Sauvegarder et arrêter l’ancien serveur avant migration, puis réinstaller et redémarrer. Les jobs de l’ancienne installation ne réutilisent pas leur autorisation après restauration ou transfert ; les résultats terminés restent consultables avec les droits courants.

OIDC : la signature du JWT est vérifiée à la soumission. Le job conserve son échéance et l’empreinte de configuration, pas le JWT. Il ne réalise pas une nouvelle consultation de l’IdP pendant le calcul. La qualification de l’IdP réel reste distincte.

Recette : `python scripts/demo_jobs.py`. Une instance isolée met en file le planning partagé et les trois expériences Asteria, annule un cinquième job, puis un processus worker termine brutalement après son claim. Après redémarrage, le bail est repris, les quatre calculs terminent, les résultats sont relus via MCP et retrouvés à l’identique après restauration. Rapport : tmp/demo-asteria/jobs.json.
