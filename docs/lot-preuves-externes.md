# P03 - Attestations d'exécution externe

Contrat `air.external-test-proof/0.35`, adaptateur `air.python-unittest/1`, non publié.
Il complète [les avis de conception P03a](lot-qualification-preuves.md). L'adaptateur qualifié reçoit
le résultat d'une suite Python unittest explicitement choisie, épinglée par SHA-256 et exécutée hors du
serveur AIR. Aucun code ni commande provenant d'un rapport, d'une source ou d'un appel HTTP n'est exécuté
par le serveur. SQLite et PostgreSQL utilisent les mêmes reçus immuables, sans nouvelle table SQL.

## Chaîne de confiance et portée

L'opérateur enregistre une clé publique **Ed25519**, l'identité URI de l'exécuteur, ses namespaces, les
empreintes des suites autorisées, les environnements exacts, la période de confiance et l'âge maximal
d'une preuve. La politique d'accès doit accorder explicitement `attest` à cette identité. Ni un rôle admin
HTTP ni un texte importé ne peuvent enregistrer cette confiance : les commandes de clés sont locales à
l'opérateur du registre. Une nouvelle clé utilise un nouvel identifiant ; une clé révoquée ne se réactive pas.

AIR émet un challenge avec nonce, identité, instance, politique, suite, baseline, cas, oracle/acceptation/entrées,
environnement et identifiant d'exécution. La fenêtre est explicite, au plus 24 heures et contenue dans celle
de la clé. Le rapport signé reprend le challenge exact, le nonce et les dates d'exécution. La signature
utilise la canonisation JSON RFC 8785 ; le vérificateur impose Ed25519, sans choix d'algorithme fourni par
le rapport. [API cryptographique utilisée](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).

Le serveur vérifie la signature, le mandat courant, l'identité, les empreintes, la fenêtre et la fraîcheur.
Le challenge ne peut recevoir qu'un résultat : un import identique est idempotent tant que son autorité
reste valide ; un résultat différent pour le même challenge est refusé. Chaque test a un identifiant unique.
Zéro test est refusé ; un test ignoré ou en échec attendu rend le résultat INCONCLUSIVE, un échec/erreur ou
succès inattendu donne FAIL. Seule une liste non vide entièrement PASS peut recevoir la qualification positive.

L'import rend un brouillon de `VerificationRun`. Après dépôt dans une baseline fermée contenant toutes les
entrées d'origine inchangées, une revue indépendante avec `scope: EXECUTED_TEST` peut lui attribuer
`VERIFIED_EXTERNAL_TEST`. Une signature seule ne ferme pas la porte. La qualification fixe aussi le reçu
d'import et disparaît à la lecture après retrait du mandat, révocation de clé, expiration, modification de
politique ou contexte différent. Deux runs qualifiés concurrents restent en conflit jusqu'au retrait explicite
d'une revue. Le relecteur ne peut être l'exécuteur de la preuve.

`verified_cases` compte uniquement ces tests externes qualifiés ; `qualified_design_cases` reste réservé
aux avis de conception et aux modèles reproduits. La porte n'accorde aucune autorisation d'agir. Un TEST
planifié n'est pas une exécution ; une exécution FAIL ou un conflit empêche VERIFICATION d'être MET.

## Installation et parcours automatisable

Le socle ne charge aucune bibliothèque cryptographique pour les dossiers et avis locaux. Activer seulement
cette option sur le vérificateur et le runner avec `python -m pip install -c constraints.txt ".[proofs]"`. Elle n'exige ni IdP,
PostgreSQL, Docker, Node ni cloud. Sans cette option, une demande de preuve externe est refusée explicitement.

1. Choisir un fichier de tests **de confiance** et calculer son SHA-256. Le runner exécute ce fichier sous
   le compte de l'opérateur ; ce n'est pas une sandbox. Approuver aussi ses imports et son environnement.
2. Créer les clés avec `python -m air.proof_runner keygen <nouveau-repertoire-prive>`. Les clés sont écrites
   dans `private.json` et `public.json`, jamais affichées. Conserver la clé privée uniquement sur le runner.
3. Préparer un document de confiance avec `key_id`, `executor`, `public_key`, `namespaces`, `not_before`,
   `expires_at`, `max_age_seconds`, `suite_digests` et `environments` (id/révision/digest). Accorder `attest`
   à l'exécuteur dans `access-policy.json`, puis `air --home <home> proof-key-register trust.json`.
4. Préparer `challenge-request.json` avec `idempotency_key`, `baseline`, `case`, `environment`, `run_id`,
   `key_id`, `suite_digest`, `ttl_seconds`. Les trois références sont des épingles exactes. Exécuter
   `air --home <home> proof-challenge challenge-request.json --credential architecte.json` et conserver
   le JSON retourné comme `challenge.json`.
5. Exécuter `python -m air.proof_runner run --challenge challenge.json --suite tests.py --key <prive>/private.json
   --output signed.json`. La sortie de protocole indique le nombre et le succès des tests ; les sorties libres
   et exceptions des tests ne sont pas incorporées à l'attestation. Un processus défaillant ou une suite
   modifiée pendant son exécution ne produit pas de signature.
6. `air --home <home> proof-import signed.json --credential architecte.json`, déposer le brouillon retourné,
   figer une nouvelle baseline puis obtenir la revue indépendante explicite. Lire le résultat via
   `air readiness`, HTTP ou `air_assess_readiness` ; les livrables citent les reçus.
7. Retirer une clé avec `air --home <home> proof-key-revoke revoke.json`, où le document contient `key_id`
   et `rationale`. Réexécuter avec une nouvelle clé et un nouveau challenge pour renouveler une preuve.

HTTP expose seulement `POST /v1/proofs/challenges` et `POST /v1/proofs/import`, sous identité et droits
courants. Les opérations de confiance et de signature restent hors du catalogue MCP. Les clients lisent
le même résultat de qualification ; le catalogue MCP contient toujours 78 outils avant filtrage.

## Limites de la réception

Une signature prouve l'attestation de la clé autorisée. Elle ne prouve pas l'absence de compromission du
runner, l'identité physique de sa machine ou la qualité de l'oracle choisi. L'environnement épinglé relève
du mandat de l'exécuteur ; aucune attestation matérielle n'est revendiquée. La suite est épinglée, mais les
imports Python et dépendances doivent être maîtrisés par l'opérateur. Seul l'adaptateur unittest décrit ici
est reçu ; JUnit, fournisseurs CI et autres formats exigent leur propre qualification.

La fraîcheur et la provenance de cette attestation sont vérifiées. La représentativité statistique des
`RuntimeObservation` servant à une simulation reste une obligation de modèle en P11 ; une déclaration
numérique ne devient pas une mesure authentifiée par cette extension.

Une restauration conserve rapports et reçus historiques mais change la politique et les identifiants de
connexion. Elle doit donc retirer leur effectivité. Réenregistrer la confiance dans la nouvelle installation,
émettre de nouveaux challenges et revoir les dossiers avant de revendiquer de nouvelles preuves effectives.

La recette `scripts/demo_metier.py --qualify-external-proofs` exécute trois suites fictives : idempotence
SAV, rejet de mesure périmée d'atelier, borne exclusive des accès. Ces trois tests supplémentaires ne sont
pas les neuf scénarios métier d'origine ; aucun ERP, atelier ou IAM réel n'est contacté.
