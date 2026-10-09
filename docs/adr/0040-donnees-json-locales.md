# ADR 0040 - Schémas et payloads JSON locaux autorisés

Statut : accepté pour le binding expérimental air.data/0.23.

Le modèle distingue concepts, autorités de données, entités, schémas, messages et événements. Les six types DRAFT ajoutés ne modifient pas les droits effectifs ni les anciens profils. Les identités et attributs locaux sont explicites ; relations sémantiques génériques et contraintes d’entité exécutables restent hors de ce premier binding.

La validation prend une baseline et un sujet exacts ainsi qu’un manifeste de payload. Le schéma lui-même provient exclusivement d’un manifeste local dont l’ArtifactRef correspond entièrement au modèle. Les droits sur la baseline et sur les artefacts sont contrôlés par les services existants, y compris les gardes de contexte des captures.

Un sous-ensemble fermé de JSON Schema 2020-12 accepte seulement des objets plats et des propriétés scalaires. Les références et autres mots-clés non pris en charge sont refusés avant validation ; aucune récupération réseau n’est effectuée. Schéma et payload sont chacun bornés à 1 MiB, avec limites de profondeur, nombre de valeurs, précision numérique et diagnostics.

Les JSON externes utilisent Decimal pour éviter les conversions binaires approximatives. Un typechecker explicite conserve la sémantique entière de 1.0 et 1e2, tout en refusant 1.1 pour integer. Le parseur des modèles AIR n’est pas élargi. Les rapports ne contiennent pas de nombres Decimal ni de payload : ils lient les octets par empreinte et décrivent les contrôles exécutés.

Forme du schéma, mapping des champs et forme du payload ont des statuts distincts. Une forme valide ne prouve ni le sens d’une transformation, ni la vérité d’un événement, ni l’exécution des scénarios métier. CLI, API et MCP partagent ce calcul pur ; SQLite/local et le schéma SQL 6 restent inchangés.
