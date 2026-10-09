# Données, schémas et messages - tranche 23

Binding expérimental air.data/0.23 qualifié sur SQLite et PostgreSQL 18.6, issu des pages 45–46 du white paper. Six types DRAFT sont implémentés dans ce binding : Concept, DataAuthority, DataEntity, DataSchema, Message et Event. Le profil compte 44 types de données ; les neuf profils précédents gardent leurs membres et empreintes. Le schéma SQL reste 6 et aucun service externe n’est ajouté.

## Records et limites

Concept référence un Domain exact et un steward URI ; semantic_relations doit rester vide tant que Relationship n’est pas implémenté. DataAuthority conserve un Scope, des opérations et des politiques textuelles ; aucune permission serveur n’en découle. DataEntity référence Concept et DataAuthority et décrit 1 à 128 attributs. AttributeSpec air.attribute/0.23 contient name, value_type (Boolean, Text, Integer, Decimal ou Instant), required et description. FieldRef air.field/0.23 contient name, un identifiant local ASCII borné à 64 caractères. Les attributs, champs d’identité et de corrélation sont des ensembles canonicalisés par nom, sans construction implicite d’une clé concaténée. Les champs d’identité doivent être des attributs requis ; constraints doit être vide dans ce binding.

DataSchema lie format JSON Schema, dialect_version 2020-12, un ArtifactRef application/json conservé localement et des DataEntity/Message représentés. Message référence son schéma, sa signification, une classification déclarée, des champs de corrélation et une clé d’idempotence facultative. Event référence son schéma de payload, une signification, un champ d’occurrence, des corrélations et éventuellement un SemanticContract de livraison. Les FieldRef dans un schéma externe sont vérifiés par le service explicite de validation ; la fermeture du modèle seule ne prétend pas les résoudre.

## Sous-ensemble JSON exécutable

Le binding air.flat-json/0.23 accepte un objet plat JSON Schema 2020-12 avec properties, required et additionalProperties=false. Les 1 à 128 propriétés sont scalaires : string, integer, number ou boolean. Les formats date-time et uri, tailles de chaînes, bornes numériques et enums scalaires bornées sont disponibles. Les mots-clés admis sont fermés. Références de schéma, compositions, patterns, code et résolution réseau sont refusés avant appel au validateur. Ce binding ne revendique pas JSON Schema complet ni la compatibilité sémantique de transformations.

La DataSchema doit désigner le manifeste d’un artefact immuable local dont le descripteur complet correspond exactement au modèle. Schéma et payload sont limités chacun à 1 MiB ; doublons, nombres non finis, surrogates Unicode isolés, plus de 10000 valeurs ou profondeur supérieure à 48 sont refusés. Les nombres JSON externes sont lus en Decimal exact, limités à 38 chiffres significatifs et à un exposant de valeur absolue 128. Un nombre comme 1.0 est accepté par le type JSON integer ; 1.1 ne l’est pas. Le parseur strict des modèles AIR reste inchangé.

Les attributs DataEntity représentés correspondent par nom et type aux propriétés du schéma. Les champs requis du modèle restent requis dans le schéma. La clé d’idempotence doit être un champ requis string ou integer ; le champ d’occurrence d’un Event doit être un champ requis string au format date-time. Ces contrôles n’établissent ni la vérité d’un événement ni une garantie d’exécution idempotente d’un système externe.

## Service commun

La requête contient baseline et subject exacts (id, revision, digest), et payload_artifact avec la référence exacte de son manifeste. subject doit être un Message ou Event membre de la baseline. data-validate, POST /v1/data/validate et MCP air_validate_data appellent le même service. Toute la baseline et chacun des artefacts doivent être autorisés, y compris leurs éventuelles gardes de contexte.

Le rapport distingue schema_validation, field_mapping_validation et payload_validation : SATISFIED, VIOLATED ou NOT_EXECUTED. Une forme de schéma invalide arrête les contrôles suivants ; un mapping incohérent empêche la validation du payload. Les erreurs de droits et d’intégrité restent des erreurs. Un code de sortie CLI nul signifie que le calcul a été effectué : il faut lire les statuts du rapport pour connaître sa conclusion. Le rapport contient les références, empreintes des octets et au plus 128 diagnostics triés ; il ne recopie pas le payload. Aucune autorisation, ingestion d’événement ou qualification sémantique n’est effectuée.

## Recette

scripts/demo_data.py reprend les trois dossiers de workflows et ajoute une réclamation SAV, une proposition d’inspection et une proposition de révocation IAM. Chaque dossier contient 68 objets. Les payloads valides, invalides et formes d’événement sont comparés par CLI/API/MCP puis après restauration. Les neuf cas métier existants restent NOT_EXECUTED. La réception de la tranche exige aussi les tests de limites, décimaux exacts, schémas interdits, droits sur les artefacts et transfert entre moteurs.

## Réception de cette tranche

369 tests passent sur chaque moteur, dont vingt-cinq cas propres aux données. Les trois parcours de 68 objets et DEMO-METIER-1 passent. La validation de forme reste distincte de la réception des neuf cas métier, de la vérité des événements et de toute permission d’agir.
