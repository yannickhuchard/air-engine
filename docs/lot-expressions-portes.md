# Tranche 03 - AIR-Expr et portes de validation

Version 0.3.0.dev1, 19 septembre 2026. Implémentation de D.4 du white paper,
page 65, selon le sous-ensemble explicite ci-dessous. Le moteur est
`air.expr/0.3`, le profil de calcul `air.validation/0.3`. Les objets persistés
restent au profil `air.foundation/0.2` : aucun digest ni schéma SQL modifié.

## Utilisation

Depuis la racine, avec Python du venv :

```bat
.venv\Scripts\python.exe -m air expr-evaluate examples\expression.json
.venv\Scripts\python.exe scripts\demo_validation.py
```

Le premier exemple calcule 5 ETP ≤ 4 ETP et retourne VIOLATED, code de sortie 1.
Il illustre une comparaison, sans exécuter de planning ou de réservation.
Le second rejoue les trois dossiers dans une seule SQLite temporaire isolée ;
rapport complet dans `tmp/demo-asteria/validation.json`.

`air expr-evaluate fichier.json` exécute localement le même interpréteur que
`POST /v1/expressions/evaluate`. `air gate-validate demande.json` appelle
`POST /v1/validations` avec les identifiants protégés du répertoire AIR.
Les options `--home`, `--port` et `--credential` suivent les autres commandes.
Les deux routes exigent une identité reader, editor ou admin. Aucun droit
d’écriture ni effet sur les révisions, l’audit ou un système externe.

Les sorties CLI sont JSON UTF-8, y compris dans les redirections Windows.
Code 0 pour une expression KNOWN/SATISFIED ou une porte PASSED ; code 1 pour
VIOLATED, UNKNOWN, CONFLICTING, erreur, budget dépassé ou porte BLOCKED.
Une évaluation d’expression reçue retourne HTTP 200 avec son statut d’exécution,
y compris ERROR. Une demande de porte invalide retourne 422 ; un digest de
baseline différent retourne 409. Une porte bloquée reste un rapport HTTP 200.

## Contrat des expressions

La demande contient exactement `expression` et `inputs`. Une expression contient
`language: AIR-Expr`, `language_version: 0.1`, `result_type`, `ast` et éventuellement
`required_inputs`, liste de `{name, type}`. Chaque référence externe doit être
déclarée, même si sa valeur manque. Les noms sont des clés exactes : les points
n’exécutent aucune navigation d’objet ou introspection Python.

```json
{
  "expression": {
    "language": "AIR-Expr",
    "language_version": "0.1",
    "result_type": "Boolean",
    "required_inputs": [{"name": "sensor.age", "type": "Duration"}],
    "ast": {"op": "lte", "args": [
      {"ref": "sensor.age"},
      {"literal": {"type": "Duration", "value": "60"}}
    ]}
  },
  "inputs": {"sensor.age": {"type": "Duration", "value": "75"}}
}
```

| Type | Représentation et limites |
| --- | --- |
| Boolean | `true` ou `false`, sans conversion implicite |
| Text | Chaîne Unicode, 10 000 caractères maximum |
| Integer | Entier exact dans ±9 007 199 254 740 991 |
| Decimal | Chaîne décimale sans exposant, au plus 38 chiffres significatifs et 18 décimales |
| Quantity[unité] | Même décimal, unité nominale explicite, par exemple Quantity[FTE] ou Quantity[h] |
| Instant | UTC Z, date valide, précision maximale microseconde |
| Duration | Secondes décimales exactes ; aucun calendrier implicite |
| Reference | `{id: URI, revision: entier positif}` ; comparaison, sans résolution externe |
| Collection[T] | Au plus 256 valeurs typées homogènes ; collections imbriquées exclues |

Chaque valeur connue s’écrit `{type, value}`. Une entrée incertaine s’écrit
`{type, state: UNKNOWN}` ou `{type, state: CONFLICTING}`, sans valeur choisie.
Les éléments d’une collection sont eux aussi typés et peuvent être incertains.
Une référence déclarée mais absente fournit UNKNOWN et un diagnostic.

Les nœuds autorisés sont `literal`, `ref`, `{op, args}` et les quantificateurs
`{op: every|some, over, predicate}`. Dans le prédicat, `ref: $item` désigne
l’élément courant ; une quantification imbriquée possède son propre élément.
Les collections sont explicitement fournies, jamais obtenues par appel externe.

| Opérateurs | Sémantique |
| --- | --- |
| and, or, not | Booléens ; and/or ont exactement deux arguments |
| eq, ne | Deux valeurs scalaires de même type |
| lt, lte, gt, gte | Nombres compatibles, textes ou instants de même type |
| add, sub | Même type numérique, même unité pour Quantity ; Duration en secondes |
| mul, div | Integer ou Decimal ; division d’entiers produit Decimal |
| in, length | Appartenance à une collection du même type ; nombre d’éléments |
| every, some | Quantification finie ; every vide = vrai, some vide = faux |

Pas de conversion Integer/Decimal implicite, de conversion d’unité, de produit
dimensionnel ou d’arithmétique calendaire. La division inexacte telle que 1/3,
la division par zéro, un dépassement de précision ou de plage produit ERROR,
résultat UNKNOWN. Aucun arrondi silencieux. Les chaînes sont comparées par points
de code Unicode, sans normalisation linguistique. Le calcul ne consulte jamais
l’heure courante : une date de référence doit être fournie explicitement.

Faux ET UNKNOWN = faux ; vrai ET UNKNOWN = UNKNOWN ; vrai OU UNKNOWN = vrai ;
faux OU UNKNOWN = UNKNOWN ; NON UNKNOWN = UNKNOWN. CONFLICTING reste distinct et
prioritaire dans les combinaisons booléennes, même avec un autre opérande décisif.
Les erreurs ne sont pas masquées par une branche décisive : tout l’AST est typé,
et les opérandes sont évalués sans court-circuit. NOT_APPLICABLE n’est jamais
une valeur d’expression ; seule l’applicabilité d’une règle peut le produire.

## Limites et déterminisme

Entrée JSON/YAML limitée à 1 Mio, AST à 2 048 nœuds et profondeur 24, collections
à 256 éléments, déclarations à 256 entrées. Chaque visite d’un nœud consomme une
étape ; maximum 10 000 étapes par évaluation autonome. Les règles d’une porte
partagent un budget de 20 000 étapes, y compris leur applicabilité. La validation
structurelle est bornée séparément par la taille des entrées et des AST.

Opérateurs sur liste fermée ; aucun eval, import, accès réseau, fichier, LLM,
extension exécutable ou récursion sans limite. Le résultat sépare `execution`
(EXECUTED, ERROR, BUDGET_EXCEEDED), `result` (KNOWN pour un scalaire connu,
SATISFIED/VIOLATED pour un booléen, UNKNOWN ou CONFLICTING), valeur typée,
diagnostics et coût. Le digest SHA-256 porte sur les octets JSON canoniques JCS.
L’ordre des listes et le texte des décimaux participent au digest de la demande.

## Contrat des portes

Une demande possède exactement :

```json
{
  "profile": "air.validation/0.3",
  "gate": "foundation-review",
  "baseline": {"id": "urn:exemple:baseline", "revision": 1, "digest": "sha256:..."},
  "rule_set": {"id": "urn:exemple:controles", "version": "1", "rules": []},
  "inputs": {}
}
```

Ce squelette est illustratif : fournir le digest exact retourné par baseline-create
et une liste de 1 à 64 règles. Les fichiers `dossiers/*/validation.json` du jeu
Asteria donnent les règles complètes ; `scripts/demo_validation.py` construit
la demande avec les références exactes de chaque baseline.

Une règle contient `id`, `version`, `mandatory` booléen, `method`
(EXPRESSION ou MANUAL), une expression Boolean `applicability`, et un `predicate`
Boolean seulement pour EXPRESSION. Les identités de règle doivent être uniques.
Les préfixes AIR- et air. sont réservés : les règles fournies ne peuvent pas se
présenter comme des contrôles normatifs exécutés par AIR.

Les seules propriétés calculées depuis la baseline vérifiée sont :
`baseline.closed`, `baseline.member_count`, `baseline.blocking_unknown_count` et
`baseline.contested_assertion_count`. Les autres entrées ont le préfixe `inputs.`.
Un appelant ne peut pas remplacer ces faits de baseline. Ces entrées restent
des déclarations de l’appelant, sans qualification de leur source ou de leur fraîcheur.

La porte applique ces règles :

- Applicabilité fausse : NOT_APPLICABLE, prédicat NOT_EXECUTED.
- Applicabilité inconnue ou contradictoire : résultat correspondant, prédicat NOT_EXECUTED.
- Contrôle MANUAL applicable : UNKNOWN/NOT_EXECUTED, aucune revue inventée.
- Une règle obligatoire autre que SATISFIED/NOT_APPLICABLE bloque.
- Une erreur ou un budget dépassé bloque, même pour une règle facultative.
- Les Unknown BLOCK non résolus et les Assertion CONTESTED de la baseline bloquent
  toujours, même si le jeu de règles fourni ne les mentionne pas.
- Une règle facultative violée ou incertaine demeure visible sans bloquer à elle seule.

Le rapport expose PASSED/BLOCKED séparément des résultats individuels. Il contient
la baseline exacte, les digests de la demande, du jeu de règles, des entrées et
du rapport, le moteur, les faits dérivés, résultats, motifs de blocage, couverture
et coûts. À entrées identiques, le rapport est identique ; aucune date d’exécution
volatile n’entre dans ce rapport de calcul. Conserver demande, export de baseline
et rapport permet le rejeu avec la même version du moteur.

**PASSED concerne exclusivement le jeu de règles fourni et cette porte de diagnostic.**
Le rapport porte `decision_ready: false`, `authorization_granted: false` et
`policy_authority: CALLER_SUPPLIED_DIAGNOSTIC_ONLY`. Il ne valide ni le choix des
règles par une autorité métier, ni leur exhaustivité, ni une admission. Les demandes
d’approbation ou de dérogation auto-déclarées sont refusées par le contrat strict.

## Réception et suite

Les trois dossiers ont des contrôles synthétiques distincts : SAV UNKNOWN,
atelier VIOLATED, identités CONFLICTING. Les variantes d’entrées corrigées
produisent SATISFIED pour leur prédicat ; les trois portes restent BLOCKED,
car leurs inconnues et revues obligatoires restent ouvertes. Le seuil de fraîcheur
atelier de 60 secondes est expérimental et ne constitue pas une décision métier.

Cette tranche n’ajoute pas Expression/ValidationRule/ValidationReport comme objets
meta/body persistables dans une baseline : ce sont des contrats de calcul versionnés,
préparant ces types. Les révisions existantes et AIR-V003 conservent leur périmètre.
Les 83 autres règles normatives restent non exécutées ; l’interpréteur ne constitue
pas à lui seul leur implémentation. Les règles de portée, sévérité, autorité,
dérogation, revue authentifiée et plugins restent à étendre.

DEMO-METIER-1 reste NOT_READY. Prochaine tranche : exigence → fonction → contrat
→ unité de construction, puis impacts, autorisations fines et vues de réception.
Voir [la recette](demonstration-trois-dossiers.md) et les preuves (document historique ou livrable local non inclus).
