# Admission locale et activation - tranche 10

L10/L13/L14, white paper §§11, 13.4–13.5 et annexe F. Le premier binding engage des ressources fictives ou déclarées par leurs responsables dans un registre AIR central. Il ne déclenche aucun ERP, équipement, annuaire ou achat. La fédération multi-autorités distante reste séparée.

## Sources d’autorité

Les offres de capacité sont déclarées par un sujet disposant d’un mandat explicite sur leur scope. Chaque offre conserve Source et Scope exacts, ressources dédupliquées, périodes, offre brute, obligations, date d’observation et échéance. Les réservations existantes sont lues du registre ; le client ne les déclare pas. Les décimales sont stockées en micro-ETP entiers pour préserver les calculs sur SQLite et PostgreSQL.

Les mandats métier proviennent d’une politique engagée dans SQL. Une modification de politique devient effective au commit du registre d’autorité. Le fichier local sert de configuration et de contrôle d’accès ; une discordance avec la politique SQL bloque les nouvelles décisions engageantes. Une lecture en cache ou un champ approved envoyé par le client ne confère aucune autorité.

## Proposition et revue

Une proposition épingle les baselines de conception, unités, offres et fenêtres. Le serveur construit ses entrées de capacité depuis le registre et recalcule le planning avec le moteur déterministe. La couverture structurelle et les limites restent visibles. L’admission de capacité ne signifie pas réception des systèmes métier.

Un autre sujet habilité examine le digest exact de cette proposition. Son reçu fixe politique, portée, décision et échéance. Le demandeur ne peut fabriquer son approbation ni réutiliser une revue visant une autre proposition.

## Transaction d’admission

Sous le verrou du périmètre d’invariants, contrôler identité et mandats courants, politique, proposition exacte, revues, offres et réservations actuelles. Recalculer la faisabilité sur la disponibilité restante. Inscrire reçu, réservations et audit dans une transaction. Même acteur/clé/contenu retrouve le résultat ; clé réutilisée pour un autre contenu est refusée.

Deux demandes concurrentes ne peuvent consommer ensemble plus que l’offre disponible au moment du commit. Une baisse ultérieure d’une capacité observée déclenche une réévaluation ; elle ne supprime pas silencieusement le travail déjà engagé. Les opérations de calcul seules ne réservent ni ne libèrent rien.

## Activation et reprise

L’activation réexamine fenêtre courante, mandats, politique, offre, revues et réservations. Une condition perdue juste avant activation bloque l’autorisation. Le reçu d’admission historique et les réservations existantes restent traçables. Aucun appel externe n’est exécuté par ce binding.

Une libération avant activation doit être explicite et habilitée. Le travail ayant reçu une autorisation d’activation est protégé ; il ne doit pas être libéré par une simple révocation ou expiration administrative. La réception d’avancement et la clôture d’un épisode constituent des transitions distinctes.

## Recette exécutable

Asteria : trois demandes initiales totalisant 5 ETP pour une offre nette de 4, refus transactionnel du dépassement, puis proposition collective de 3 ETP suivis de 2 ETP. Vérifier concurrence, idempotence, panne après commit, changement d’offre et de mandat, activation trop tôt ou hors fenêtre, condition perdue et conservation du travail engagé. Les résultats doivent provenir des services HTTP et du registre ; les oracles de fixtures ne sont pas des résultats.

Version source 0.10.0.dev1, schéma 4. La recette HTTP/CLI/MCP est scripts/demo_admission.py ; elle produit tmp/demo-asteria/admission.json et admission.html. Le serveur isolé est arrêté en fin de parcours. La fenêtre est translatée à l’horloge réelle du serveur pour vérifier une activation effective sans attendre octobre. Les expériences des trois dossiers restent ILLUSTRATIVE.

## Utiliser les services

Définir access-policy.json avec les sujets et mandats read, write, capacity, review, admit, activate. Exécuter la commande locale policy-set pour engager la politique dans SQL. Aucun rôle admin ne reçoit implicitement un mandat métier. Chaque changement effectif, y compris un retour à une politique antérieure, augmente une génération.

| CLI, fichier JSON en argument | Outil MCP | Effet |
| --- | --- | --- |
| capacity-publish | air_capacity_publish | Publier une observation avec expected_offer exact ou null pour la première |
| capacity-get | air_capacity_get | Lire offre et réservations courantes |
| admission-propose | air_admission_propose | Calculer et figer une proposition depuis les offres exactes |
| admission-review | air_admission_review | Accepter ou refuser la proposition avec un autre sujet |
| admission-review-revoke | air_admission_revoke_review | Retirer sa propre revue |
| admit | air_admission_admit | Recontrôler et réserver atomiquement, ou conserver un refus |
| admission-read | air_admission_read | Lire reçu et réservations sans changer leur effectivité |
| admission-release | air_admission_release | Libérer explicitement avant toute activation |
| activate | air_admission_activate | Autoriser un épisode local dans la fenêtre admise |

Les schémas exacts sont retournés par MCP tools/list et définis dans authority.py et admission.py. Tous les adaptateurs appellent les mêmes services ; les entrées supplémentaires telles que approved, actor ou existing_reservations sont refusées.

## Limites opérationnelles explicites

Le premier binding utilise une autorité SQL centrale, des pools humains disjoints et des semaines contiguës, au plus 104 périodes et 32 pools. Les quantités inconnues restent inconnues. Le catalogue normatif des types AIR n’est pas étendu par ces contrats de service expérimentaux.

Les revues expirent au plus sept jours après leur émission. Les offres et les identités de leurs déclarants sont réexaminées à l’admission et à l’activation. Une offre remplacée, un jeton expiré/révoqué ou une politique modifiée bloque une activation ultérieure, même si le reçu d’admission reste historique. La réautorisation d’un engagement existant et la clôture de travail activé sont les transitions suivantes à développer ; cette version protège leurs réservations et refuse leur libération automatique.

Un transfert ou une restauration révoque les anciennes identités. Une politique restaurée n’est pas silencieusement réengagée : policy-set et de nouvelles observations sont nécessaires avant de nouvelles décisions métier. Les projections de capacité/réservation/activation sont contrôlées contre les reçus immuables lors du transfert.

Un reçu d’activation autorise seulement un épisode de ressources local. Il ne vaut ni exécution externe, ni réception d’un ERP, d’un atelier ou d’IAM, ni preuve de présence humaine devant l’IDE.

La tranche 11 ajoute désormais le renouvellement et les clôtures déclarées sous revue. Voir lot-renouvellement-cloture.md ; les limites ci-dessus décrivent la tranche 10 initiale.
