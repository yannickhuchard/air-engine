# ADR-21 - Expressions bornées et portes de diagnostic

Statut : IMPLEMENTED_SCOPED. Date : 19 septembre 2026.

D.4 propose AIR-Expr 0.1 sans fixer tous les détails de sérialisation ou de calcul.
Le binding `air.expr/0.3` est défini dans [le contrat de tranche](../lot-expressions-portes.md).
Il utilise des littéraux et entrées typés, des références nommées déclarées,
des opérateurs fermés, des collections finies et un budget partagé par porte.

Nous choisissons des décimaux exacts bornés, sans arrondi silencieux ; des unités
nominales sans conversion implicite ; des durées en secondes et des instants UTC.
CONFLICTING reste prioritaire, car le système doit conserver une contradiction
visible même lorsqu’un autre opérande déterminerait la valeur d’un booléen.
Tout AST est vérifié avant exécution, y compris les branches inapplicables.

Les règles fournies par un appelant ne représentent pas une politique approuvée.
La porte foundation-review produit donc un diagnostic reproductible, jamais une
autorisation. Les inconnues bloquantes et assertions contestées de la baseline
sont contrôlées indépendamment du jeu fourni. La revue humaine n’étant pas livrée,
les contrôles MANUAL applicables sont NOT_EXECUTED/UNKNOWN. Les dérogations ne
sont pas acceptées. Les statuts d’exécution, de résultat et de porte sont séparés.

Les artefacts de calcul sont liés par leurs digests à la baseline, aux règles et
aux entrées. Ils ne sont pas stockés comme nouveaux types du profil foundation/0.2,
ce qui préserve ses schémas, digests et exports. Une extension persistable du
catalogue et un registre de politiques sous autorité nécessiteront leur propre
contrat versionné. Aucun changement SQL ni dépendance supplémentaire n’est requis.
