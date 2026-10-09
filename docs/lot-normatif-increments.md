# P10–P14 - Incrément de développement 0.35.0.dev1

Ces travaux suivent la demande du 28 septembre 2026. Ils ne clôturent pas les cinq
lots ni G3. La version rc9 et ses preuves P07/P08 restent distinctes.

## P10 - Temps et traçabilité

`temporal-reconstruct` / `air_reconstruct_temporal` sélectionnent les révisions
connues du registre à `known_at` et valables à `valid_at`. Les corrections reçues
plus tard ne changent pas l'historique. Les autorisations actuelles s'appliquent,
y compris aux références transitives. La sélection ne crée pas une baseline.
Le contrat est décrit dans [ADR-45](adr/0045-reconstruction-bitemporelle.md).

AIR-Expr **0.2**, moteur `air.expr/0.4`, ajoute l'opérateur explicite `convert` :
une quantité et une unité cible littérale. Le registre `air.units/1` distingue
temps écoulé, longueur, masse, information, effort de travail et ratio FTE.
Les conversions sont exactes ; une division non décimale finie reste une erreur
plutôt qu'un arrondi silencieux. FTE, jours de travail et temps écoulé ne deviennent
pas interchangeables. La version 0.1 garde ses opérations et ses résultats.
L'extension est disponible dans `expr-evaluate` et `/v1/expressions/evaluate`,
ainsi que dans les expressions des inférences, règles métier, workflows,
machines d'états, contraintes, politiques et cartes de navigation. Chaque expression
choisit explicitement 0.1 ou 0.2 ; 0.1 ne peut pas employer `convert`. Les conversions
de dimensions incompatibles sont rejetées dès la validation du modèle.

Une simulation employant 0.2 annonce `air.scenario-simulation/0.35` ; le replay
d'états et le contrôle de politique annoncent respectivement `air.state-replay/0.35`
et `air.policy-check/0.35`, avec les versions des moteurs d'expression utilisés.
Les rapports qui n'emploient que 0.1 gardent leur moteur et leur forme historiques.
Une inférence ou une règle simplement stockée n'est pas, pour autant, exécutée
ni qualifiée : leur déclaration conserve ses limites. Voir la
vérification de l'intégration (document historique ou livrable local non inclus).

`scripts/normative_report.py` génère une matrice (document historique ou livrable local non inclus) des 143 types, 84 règles,
18 opérations et 72 tâches. Il vérifie le white paper, les identifiants uniques,
les fichiers liés et leurs empreintes. Il conserve les statuts déclarés et distingue
les identifiants de tests prévus des preuves d'exécution. Un nom de type ou un fichier
présent ne peut donner la conformité. Ce rapport est un inventaire, pas un validateur
complet des prédicats normatifs.

## P11 - Synchronisation et conversions

Un pas `air.workflow-step/0.35` déclare `join: ALL` ou `ANY`. ALL attend toutes les
arêtes entrantes déclarées et commence à leur dernière arrivée ; ANY conserve la
première arrivée. Une branche requise non parcourue bloque ALL ; le résultat devient
INCONCLUSIVE. Le nouveau moteur de simulation est `air.scenario-simulation/0.35`.
Chaque pas s'exécute au plus une fois : boucles répétées et état métier mutable
restent hors de ce contrat. Les anciens pas conservent le moteur `/0.32`.

`currency-convert` / `air_convert_currency` lisent les CostItems épinglés d'une
baseline. Les taux directs sont explicites, datés, versionnés et liés à une Source
exacte. Aucun taux implicite, inversion ou consultation réseau. Les résultats
conservent montants exacts et arrondis HALF_EVEN, avec précision déclarée. Les totaux
arrondissent une seule fois et séparent nature, récurrence et période. L'authenticité
économique d'un taux fourni n'est pas attestée par son calcul.

## P12 - Publications distantes signées

`federation-trust` et `federation-revoke` sont des commandes d'opérateur local ;
elles n'existent pas comme outils MCP. L'extra `proofs` fournit Ed25519. La réception
(`federation-receive` / `air_receive_checkpoint`) vérifie signature, destinataire,
namespace, mandat courant de publication du pair, dates et autorisation locale.

Chaque message est un checkpoint complet d'une publication, identifié par pair,
agrégat et séquence. Les doublons sont idempotents ; un contenu différent pour la
même séquence est refusé. Les séquences anciennes ne font pas régresser la projection.
La révision d'une même baseline ne peut reculer ni changer d'empreinte. La lecture
(`federation-read` / `air_read_checkpoint`) recontrôle la confiance actuelle ; elle
ne remonte pas à une publication ancienne lorsque la dernière est révoquée ou périmée.

Les sources gardent leur autorité. Les checkpoints ne sont ni des imports du modèle
canonique, ni des réservations, ni une admission distribuée.

La signature côté émetteur utilise désormais `federation-keygen` puis
`federation-export`. L'outbox durable sélectionne les exports exacts d'une publication
locale ; seul son propriétaire authentifié peut la signer. Le compteur par agrégat
et destinataire résiste aux répétitions concurrentes et aux interruptions avant
commit. Les retraits sont propagés par un nouveau checkpoint. La clé privée est
lue depuis un fichier protégé ; elle n'entre jamais dans la base ni les rapports.
Le transport reste un fichier échangé explicitement : aucune synchronisation réseau
automatique n'est annoncée. Le [guide](publications-signees.md) décrit ce contrat.

## P13 - Connecteur d'observations borné

`connector-preview` / `air_preview_connector` lisent un artefact JSON déjà importé
et autorisé. Le connecteur fixe `air.observations-json/1` valide un document contenant
`observations`, prépare la requête d'ingestion et conserve le digest du contenu.
Le texte importé n'est jamais exécuté et ne peut choisir de module Python, chemin
de fichier ou URL à ouvrir. Le plafond est 512 KiB et 128 observations.

Le dépôt utilise ensuite `observation-ingest` / `air_runtime_ingest`, sous les droits
d'écriture courants. Le service revérifie que les observations correspondent
exactement à l'artefact. Le reçu conserve l'artefact et la version de connecteur.
La qualification reste DRAFT : le mapping ne prouve ni une mesure réelle ni sa
représentativité. Les anciens imports sans connecteur restent compatibles.

## P14 - Réception restante

La matrice générée aide à préparer la réception normative. Elle ne remplace pas
les cas positifs, négatifs et limites de chaque obligation. Les réceptions de
distribution, sécurité, charge, restauration et clients natifs devront porter sur
la candidate finale. Les tests locaux et les trois dossiers Asteria sont conservés ;
aucune CI n'est lancée pendant le développement.
