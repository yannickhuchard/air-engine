# Contextes de contributions et réconciliation - contrat de développement

Source : white paper §§12.3–12.4 et 13.3 ; L06.4, L11.3, L12.1. La première implémentation porte sur les publications du même registre. Un contexte épingle explicitement les contributions consultées, leur fermeture, leurs empreintes et leur état observé. Il conserve date de consultation, version de politique, lacunes et portée. Une consultation ne signifie pas que toutes les contributions de l’entreprise sont connues.

Le snapshot de contexte est un reçu de service immuable. Sa création et la lecture des états de publication/révocation sont sérialisées avec leurs écritures. La reprise par même acteur et même clé retrouve le même contexte ; une nouvelle clé produit une nouvelle observation. Un changement ultérieur de politique ou une révocation ne réécrit pas l’ancien contexte. Une lecture vérifie toujours les droits actuels sur toute la fermeture.

La réconciliation compare les versions des identités partagées, signale les assertions contestées et inconnues ouvertes, et lie les écarts aux contributions concernées. Les divergences de révision appellent un examen : elles ne prouvent pas automatiquement une incompatibilité sémantique. Le résultat conserve NOT_EXECUTED pour contrats non formalisés, capacité engagée et arbitrage d’autorité. Aucune fusion, modification de source ou résolution automatique n’est produite.

Un contexte historique peut être rejoué avec son moteur déclaré ; une réévaluation courante crée un autre contexte. La fraîcheur des informations métier n’est pas déduite de la date de lecture du registre. Une réconciliation sans écart détecté ne permet ni admission ni activation.

## Commandes disponibles

context-create reçoit idempotency_key, publications (références id/digest) et purpose. context-read et reconcile reçoivent context (id/digest). Les commandes utilisent les mêmes options --credential/--port que les autres services. API : POST /v1/contexts, /v1/contexts/read, /v1/reconciliations. MCP : air_get_context, air_read_context, air_reconcile.

La commande discover reçoit namespace, include_unavailable, page_size (1–20) et cursor (null au départ). Elle fournit des références publiées lisibles et un curseur opaque éventuel. Le snapshot fixe la liste des publications ; les publications ultérieures demandent une nouvelle recherche. Les droits et révocations sont réévalués à chaque page. Les curseurs sont liés au sujet, à la politique et à la requête. Aucun total de publications cachées n’est retourné. Budgets : 10 000 publications par snapshot, 100 candidates examinées par page ; une page vide peut donc avoir une suite. Binding : POST /v1/packages/discover et air_discover.

Réception Asteria : `python scripts/demo_contexts.py`. Le script crée les trois contributions, publie une révision IAM de l’identité partagée, détecte sa divergence avec SAV/atelier, conserve le replay historique après révocation et écrit tmp/demo-asteria/contexts.json et contexts.html. Le contexte reste une photographie de lecture, pas un engagement.
