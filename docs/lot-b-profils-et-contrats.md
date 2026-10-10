# Compléter le bon dossier et transmettre des contrats précis

Un dossier rempli peut encore oublier une dimension entière. Le lot B ajoute
des questions selon le contexte du projet et des spécifications d’interface
que fournisseur et consommateur peuvent utiliser séparément pour construire.
Les vues, le CLI et le MCP utilisent les mêmes services déterministes.

## Choisir les questions utiles

Le nouveau profil de modèle `air.build-design/0.35` conserve les types du
profil de livraison et ajoute `DossierContext`, `InterfaceSpecification` et
`DataLifecycleSpecification`. Une ancienne baseline reste immuable et garde
ses douze critères. Le nouveau profil ajoute un treizième critère :
`CONTEXTUAL_COMPLETENESS`. Il ne transforme pas la documentation en preuve.

L’architecte choisit un ou plusieurs contextes dans un `DossierContext` possédé
par le dossier, avec périmètre et justification :

| Contexte | Questions supplémentaires |
| --- | --- |
| Service numérique | Personas, parcours, blocs, interfaces, frontières de confiance |
| Plateforme de données | Modèles logique et physique, cycle de vie, flux |
| Système physique | Équipements, opérateurs, usages physiques, défaillances, sourcing |
| Transformation organisationnelle | Processus, équipes, chaîne de valeur |
| Activité réglementée | Obligations, contrôles, mappings de conformité |

Le catalogue `air.completeness-catalogue/1` pose toujours dix questions communes :
résultats, exigences, réception, décisions, risques, réalisation, responsabilités,
finances, vérifications et qualité. Il pose ces questions même si aucun objet
n’existe. Les unités de construction exigent des cas de réception liés et un
RACI de livraison R et A explicitement rattaché à chaque unité. Une responsabilité
générale dans le dossier ne suffit pas. Chaque contrat et chaque table du contexte
sélectionné reçoivent aussi leurs contrôles propres.

`DOCUMENTED` signifie présence documentaire et relations explicites dans la
portée du contrôle. Ce n’est pas un audit de la qualité de chaque phrase, une
conformité exhaustive, une validation juridique ni une autorisation de lancement.
Les questions ouvertes restent visibles dans le site, y compris sur les dossiers
anciens qui n’ont pas encore choisi de contexte. AIR ne choisit pas à leur place.

Une exclusion contient une justification et une décision exacte. Elle reste
`EXCLUSION_DECLARED` tant qu’aucune acceptation authentifiée, indépendante de
l’auteur et effective ne couvre la baseline exacte contenant cette décision.
Révocation, expiration, perte de mandat, changement de politique ou rejet effectif
la rouvrent. Une acceptation d’une autre révision ne se reporte pas automatiquement.
Un champ déclaratif dans une décision ou une réponse d’agent ne vaut pas reçu.

## Contrats utilisables par deux constructeurs

`InterfaceSpecification` relie un `SemanticContract` à son `TechnicalBinding`
HTTP exact. Toutes les opérations doivent être spécifiées. Chaque opération
contient ses schémas JSON, préconditions et postconditions AIR-Expr, invariants
éventuels, politiques d’autorisation, idempotence, concurrence, délai, retry et
compensation. Elle contient au moins un échange valide et une requête invalide.
Les exemples nommés sont rejoués, avec contre-exemples et empreintes d’entrée.

Les schémas copiés dans la spécification doivent égaler les octets JSON parsés
des artefacts locaux conservés par le binding. Une contradiction bloque la
compilation et apparaît dans le diagnostic de complétude. Aucun schéma distant
n’est récupéré. OpenAPI est compilé par le service AIR existant, depuis les mêmes
artefacts, sans constituer une seconde vérité.

La suite fournit quatre fichiers : `interface-contract.json`, `openapi.json`,
`README.md` et `verify.py`. Le script nécessite un environnement AIR installé.
Les deux constructeurs peuvent implémenter indépendamment le contrat et remettre
leurs échanges au vérificateur. Le site propose les fichiers ; il ne les exécute pas.

`PASS_DESIGN_EXAMPLES` signifie que les exemples déclarés correspondent aux
schémas et prédicats purs. Une entrée inconnue ou un prédicat indéterminé produit
`INCONCLUSIVE`, jamais un succès implicite. Les mécanismes réels de sécurité,
stockage d’idempotence, concurrence, délais, retries, compensation, compatibilité
avec une ancienne version, effets métier et réponses d’erreur restent à recevoir
après construction. AIR vérifie seulement certaines cohérences déclaratives,
par exemple le header d’idempotence obligatoire ou un retry dangereux non protégé.

Le sous-ensemble JSON Schema est volontairement borné : type explicite, objets
avec `additionalProperties` explicite, propriétés requises, tableaux bornés,
enum/const et bornes simples. Pas de `$ref`, regex, formats ou compositions.
Maximum 256 nœuds, profondeur 12, 64 propriétés par objet et 256 éléments par
tableau. Les nombres décimaux AIR sont des chaînes précises, pas des flottants
binaires. Les prédicats utilisent Text, Boolean, Integer ou Decimal, sans effets.
Une spécification est bornée à 256 exemples et 128 conditions au total.
Le contexte lu est borné séparément à 20 000 objets et 32 MiB, le rapport de
complétude à 8 MiB. La limite d’un échange ou schéma reste 1 MiB : elle ne
doit pas être appliquée au dossier entier et bloquer les dossiers existants.

`DataLifecycleSpecification` décrit propriétaire, clés uniques, indexes,
rétention justifiée, migration et retour arrière liés à des cas de vérification.
AIR contrôle les colonnes, doublons et clé primaire non nullable. Ce sont des
plans pour réaliser : aucune migration ni suppression de données n’est exécutée.

## Utiliser avec un agent ou le CLI

| Besoin | MCP | CLI |
| --- | --- | --- |
| Lire les questions et écarts | `air_assess_completeness` | `completeness-assess` |
| Préparer la suite du contrat | `air_compile_interface_suite` | `interface-suite` |
| Vérifier un échange fourni | `air_verify_interface_exchange` | `interface-verify` |

Les requêtes portent la baseline exacte `{id, revision, digest}` ; les deux
opérations d’interface portent aussi la spécification exacte. `profiles` dans
la requête de complétude est un aperçu, sans choix enregistré ni approbation.
`content: "DIGESTS"` permet d’inspecter les fichiers sans exporter leur contenu.
Les trois outils sont en lecture seule, soumis aux mêmes droits que le dossier.

```text
air --home .air completeness-assess context.request.json --credential architect.json
air --home .air interface-suite suite.request.json --credential architect.json --workspace contract --apply
air --home .air interface-verify exchange.request.json --credential architect.json
```

Commencer par `air_describe_type`, proposer les trois types dans le parcours
de contribution habituel, valider à blanc et figer après accord. Régénérer le
site avec `air deliverables` : l’accueil ouvre `completeness.html`, ses questions,
sources exactes et suites. Le guide et les skills officiels exposent ce parcours.
Une reconnexion ou redécouverte des outils peut être nécessaire dans le client.

## Démonstration reproductible

```text
python scripts/demo_build_design.py --output tmp/build-design-reception
```

Le répertoire doit être neuf et `AIR_DATABASE_URL` absent. Deux prototypes
fictifs Python indépendants, sans import l’un de l’autre ni du moteur AIR,
échangent réellement par HTTP local. Le fournisseur calcule un devis en centimes ;
le consommateur construit la requête et interprète le résultat selon le contrat.
La recette couvre cent quantités, un rejeu, un conflit de clé et quatre entrées
invalides. Le CLI compile, matérialise et rejoue la suite, détecte un prix faux
et produit le site. Le registre reste inchangé par les lectures et vérifications.

Cette recette prouve une intégration technique de prototypes. Elle ne constitue
ni réception par deux équipes humaines, ni produit déployé, ni qualification
universelle des clients agentiques. Les trois dossiers Asteria sont rejoués
séparément selon DEMO-METIER-1. Aucune CI n’est déclenchée.

Les paquets de construction et l’acceptation des équipes constituent le
[lot C](ROADMAP_REFERENCE.md). Les autres protocoles, profils sectoriels et
compatibilité sémantique entre versions restent des extensions explicites.
