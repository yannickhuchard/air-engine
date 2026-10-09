# Renouvellement et clôture - tranche 11

Version source 0.11.0.dev1, schéma 5 ; 226 tests passent sur SQLite et PostgreSQL 18.6 ; recette HTTP reçue. L13–L15.

La version 0.10 conserve les réservations lorsque l’autorité ou la capacité change. Il faut permettre de réexaminer les engagements sans effacer leur histoire ni libérer un travail actif. Les nouvelles transitions demeurent locales et n’appellent aucun système métier.

## Réautoriser un engagement

Préparer une nouvelle proposition liée au reçu d’admission exact, aux mêmes unités et aux mêmes fenêtres réservées. Les offres de ressources courantes doivent couvrir les mêmes pools ; les quantités, baselines et séquences ne peuvent être modifiées par un renouvellement d’autorisation. Recalculer en excluant uniquement les propres réservations de cette admission, puis demander une revue indépendante de cette nouvelle proposition.

Sous verrou SQL, comparer la génération d’autorisation attendue, vérifier politique, offre, identité, revue et réservation courantes, puis avancer la tête d’autorisation dans une transaction. Une répétition est idempotente ; une génération périmée échoue. Aucun nouvel engagement n’est créé et aucune capacité n’est comptée deux fois. Les anciens reçus conservent leurs cibles et leur histoire.

L’activation suivante utilise la tête d’autorisation engagée. Un épisode déjà autorisé reste traçable ; une actualisation ne crée pas une seconde autorisation pour le même épisode. Changer le contenu ou le calendrier d’un travail relève d’un aménagement distinct.

## Clôturer un épisode

Un responsable habilité déclare la fin ou l’abandon d’un épisode exact, avec preuve explicitement référencée, portée et justification. La déclaration et sa revue indépendante restent distinctes de la vérification d’un système réel. Aucune promotion automatique en fait établi ou en VerificationCase réussi.

Après réception de cette clôture, le responsable des engagements peut libérer explicitement les ressources. Tant qu’un épisode reste ouvert, les réservations correspondantes demeurent protégées. Une révocation, une expiration ou un arrêt du serveur ne vaut jamais clôture.

## Vérification attendue

Reprendre l’admission Asteria : changement de politique, nouvelles observations, revue indépendante, renouvellement sans réservation supplémentaire, activation suivante ; clôture avec preuve, auto-revue refusée, maintien du travail encore ouvert et libération explicite après réception. Concurrence, idempotence, migrations, sauvegarde et transfert doivent conserver ces invariants sur SQLite et PostgreSQL.

## Commandes disponibles

| CLI avec fichier JSON | MCP | Contrat |
| --- | --- | --- |
| renewal-propose | air_renewal_propose | Admission exacte, expected_authorization, nouvelles offres exactes |
| admission-review | air_admission_review | Revue indépendante de la proposition de renouvellement |
| renew | air_renewal_renew | Proposition et revues ; comparaison de génération puis commit sans nouvelle réservation |
| closure-propose | air_closure_propose | Épisode exact, COMPLETED ou ABORTED, Evidence exacte et justification |
| closure-review | air_closure_review | Revue indépendante de la déclaration de clôture |
| closure-review-revoke | air_closure_revoke_review | Retrait par le relecteur d’origine |
| episode-close | air_closure_close | Réception de la clôture avec ses revues |
| admission-release | air_admission_release | Libération explicite quand tous les épisodes ouverts sont clos |

La lecture admission-read retourne l’autorisation courante, sa génération, les épisodes ouverts/clos et les réservations. Un renouvellement prend expected_authorization=null si aucun renouvellement n’a été engagé ; sinon il épingle le reçu courant retourné par la lecture. Le renouvellement ne peut changer ni unités, ni baselines, ni fenêtres, ni quantités. L’opération admit refuse une proposition de renouvellement.

Les clôtures portent la classe DECLARED_COMPLETION. Les preuves sont épinglées et accessibles, mais la sémantique de leur pertinence doit être examinée par le relecteur. Les VerificationCase métier restent NOT_EXECUTED ; aucune assertion n’est promue automatiquement. Révoquer une revue après réception ne réécrit pas la clôture historique.

L’opération de libération porte sur l’admission complète. Elle libère aussi les réservations d’unités jamais activées : cela signifie annulation du travail prévu, pas réalisation. Les aménagements partiels, l’avancement quantifié, les compétences et les systèmes externes restent hors de ce binding.

Recette : python scripts/demo_lifecycle.py. Elle reprend les trois dossiers sur serveur HTTP réel, attend la fenêtre d’activation, renouvelle après changement de politique/identité, puis clôt deux épisodes et annule explicitement la réservation atelier non démarrée. Le rapport complet reste tmp/demo-asteria/lifecycle.json. L’instance principale n’est pas utilisée pour ces données fictives.
