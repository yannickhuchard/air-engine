# D01 — Portail SAV et orchestration des interventions

Source fictive : compte rendu d’un atelier avec la responsable SAV, deux gestionnaires,
un technicien itinérant, les équipes intégration et sécurité. Date de référence :
21 septembre 2026. Les volumes et objectifs ci-dessous sont des hypothèses à vérifier.

## Besoin et existant

Les clients signalent les pannes par téléphone ou courriel. Un gestionnaire ressaisit
le numéro d’équipement dans l’ERP puis crée une intervention. Les demandes répétées
peuvent entraîner deux déplacements ; les clients demandent où en est leur dossier.
Le pilote concerne les demandes de dépannage d’une gamme d’équipements et dix
clients synthétiques. La gestion des garanties reste dans l’ERP et sous décision métier.

Le portail doit permettre de déposer une demande, ajouter des pièces, recevoir un
accusé de réception, suivre les étapes et compléter les informations. Les agents
doivent qualifier la demande et transmettre le travail au système d’intervention.
L’objectif proposé est de réduire les ressaisies sans promettre une prise en charge
ni une couverture de garantie lors du simple enregistrement.

## Périmètre, alternatives et contrat à construire

Alternatives : formulaire et traitement semi-manuel, portail avec intégration
asynchrone, ou remplacement global de l’outil d’intervention. Comparer impacts,
inconnues et coûts ; le remplacement global est hors pilote.

Le contrat SubmitServiceRequest conserve une demande et rend un identifiant stable.
Sa clé d’idempotence est liée au client et à la soumission ; une répétition équivalente
retrouve le reçu, un contenu différent au même identifiant est refusé. Un client
ne consulte que ses équipements et demandes. Une indisponibilité de l’ERP ne
doit pas créer une confirmation fictive d’intervention. Les pièces ont des règles
de taille, de format, d’accès et de conservation à préciser.

## Parcours à démontrer

1. Relier besoins, hypothèses et exigences aux sources de ce dossier.
2. Produire le contrat, la fonction de dépôt et les unités de construction.
3. Conserver une baseline puis proposer une évolution sans réécrire son historique.
4. Montrer le parcours nominal et expliquer doublon, mauvais client et ERP indisponible.
5. Générer une vue exploitable par développement, SAV et sécurité avec lacunes visibles.

## Inconnues et critères attendus

La capacité de l’ERP à offrir une clé de déduplication fiable est inconnue. Elle doit
rester UNKNOWN jusqu’à preuve ; un texte généré par l’IDE ne clôt pas cette question.
Une demande acceptée ne signifie pas garantie acceptée. L’essai de mauvais client
doit refuser la lecture sans divulguer le dossier visé. Les mêmes sources et versions
doivent produire les mêmes résultats déterministes.

Besoin capacitaire synthétique : 2 ETP d’intégration durant les semaines 1–4,
soit 8 ETP-semaines. Le sponsor souhaite conserver cette fenêtre pour le pilote.
La préparation du dossier ne réserve pas ces ressources.
