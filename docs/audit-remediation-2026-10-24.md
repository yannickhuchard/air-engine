# Corrections de l'audit AIR du 24 octobre 2026

Préversion de développement : moteur `0.35.0.dev8`, plugin Skills-only CLI `0.1.16`.
La distribution publique conserve les limites de chaque contrôle.
G1 reste lié à rc9. Les contrôles de cette candidate ne reçoivent ni G2,
ni G3, ni une conformité normative complète.

## Ordre de travail et portée

| Étape | Réalisation locale | Réception encore distincte |
| --- | --- | --- |
| Distribution et cohérence | Matrice de versions, templates Codex/ChatGPT, workflows manuels, refus sans moteur | Installation et parcours dans les clients natifs |
| Contributions IA | Protection des engagements existants, export borné, destination/finalité et identité modèle | Politique de données et contrôle des accès aux fichiers du poste |
| Couverture du dossier | Plan de scénarios par exigence, qualité et cycle de vie | Exhaustivité et pertinence métier à revoir |
| Traçabilité des générations | Instructions/contexte/sorties retenus, usage déclaré, critères calculés par AIR | Mesures fiables d'efficacité d'un modèle et causalité |
| Construction et preuves | Parcours joint avec dépôt Git isolé, deux constructeurs fictifs, builds et tests signés | Équipes réelles et qualification indépendante |
| Exploitation et effort | Import de ledger CI, comparaison des efforts observés et estimés | Authenticité des sources, observations de production et bénéfices réels |
| Adoption et capacité | Vérificateur de séances et charge synthétique à géométrie explicite | Participants réels, objectifs et charge représentative de l'entreprise |

## Distribution

`python scripts/release_status.py` contrôle que la matrice décrit la version
du package. Son résultat distingue la qualification historique rc9, la candidate
courante, les routes clientes documentées et les observations historiques du
portail. Il ne contacte aucun service externe et ne prolonge pas une réception.

`portfolio-init` produit les exemples Codex et ChatGPT dans chaque dépôt ;
Claude reste disponible en option. Le template de workflow reste manuel.
Sans moteur installé, il échoue avec `AIR_VALIDATION_NOT_CONFIGURED`.

Construire l'archive CLI et sa marketplace locale reproductible :

```text
python scripts/build_plugin.py --variant cli --direct-marketplace --output-dir dist/cli-0.1.16
```

Les archives antérieures sont conservées. Aucune soumission au portail, connexion
native ou publication dans un annuaire n'est déduite de cette construction.

Les empreintes exactes et la qualification d'installation sont fournies comme
assets de la release publique. Les archives historiques sont conservées.

## Contexte confié à un modèle

Lire le [contrat des contributions et exports](controle-des-contributions-ia.md).
Le workflow `context-export` exige une permission d'export indépendante de la
lecture. Pour un identifiant dédié à un modèle, ajouter au sujet de la politique :

```json
"model_context": {"destination": "modele-approuve", "purpose": "conception"}
```

Cet identifiant doit posséder les droits `read` et `export_context` ainsi qu'une
entrée `context_destinations` active. Les lectures d'objets par ScopedStore et
les lectures d'artefacts appliquent aussi cette destination et les classifications
admises. Les dépendances sont contrôlées ; une vue ne masque pas un objet interdit.
L'expiration est revérifiée avant la réponse HTTP.

Les artefacts anciens sans classification explicite sont traités comme RESTRICTED
pour ces identifiants. Leurs octets et manifestes historiques restent inchangés.
Pour un nouvel artefact, fournir `classification: {"level": "INTERNAL"}` dans
`artifact-import`, ou `--classification INTERNAL` avec `artifact-upload`.
L'API binaire accepte `X-AIR-Classification`. Les valeurs possibles sont PUBLIC,
INTERNAL, CONFIDENTIAL et RESTRICTED. Ce sont des déclarations de classification,
pas une détection automatique du contenu sensible.

Un export explicite peut sélectionner une fermeture autorisée dans une baseline
contenant d'autres objets plus sensibles. Ces autres objets ne sont pas exportés.
Une identité liée ne choisit pas une autre destination ou finalité elle-même.
Les accès directs aux fichiers par un client et les identifiants non liés restent
sous leurs propres contrôles. Aucun pare-feu du poste ou DLP global n'est livré.

## Couverture d'une solution

`DossierContext.assurance_plan` est optionnel. Pour l'adopter, fournir :

- `requirements` : une ligne par Requirement MUST, avec `requirement`, `goal`,
  `happy`, `failure`, `recovery` et une justification `rationale`.
- `quality` : une ligne par QualityRequirement MUST, avec `requirement` et `case`.
- `lifecycle` : un cas distinct par kind MIGRATION, ROLLBACK et RETIREMENT,
  avec `case` et `rationale`.

Toutes les références sont typées et fermées dans la baseline. Les trois cas
d'une exigence sont distincts et ciblent sa chaîne de construction. Le Goal
possède mesures et cibles connues ; une qualité MUST porte une cible connue,
un scope et une source. Son cas cible la QualityRequirement exacte et utilise
la méthode déclarée ; MONITORING prévoit un cas TEST à réaliser ultérieurement.
Une exclusion suit la revue effective de la baseline, comme les autres questions.

Les écarts apparaissent dans `completeness-assess`, puis dans le critère de
complétude contextuelle de readiness. Les dossiers sans plan conservent leurs
contrôles précédents. Les liens et catégories de scénarios restent déclarés :
ils ne prouvent ni leur pertinence sémantique ni leur exécution.

## Générations, tests et observations d'effort

`generation-record` et `generation-read` conservent un reçu `air.generation-trace/1`.
La requête relie `before`, `after`, `context_export`, `instructions`, `outputs`,
`provider`, `model`, `client_version`, `tools`, `usage` et une clé d'idempotence.
AIR recalcule les critères fermés et les régressions des deux baselines exactes.
Les instructions et sorties sont des artefacts autorisés. Le modèle, les appels
d'outils et la consommation restent déclarés par le client. Aucun raisonnement
interne privé n'est demandé et aucune attestation du fournisseur n'est inférée.

`ci-ingest` consomme un artefact JSON `air.ci-ledger/1` jusqu'à 512 KiB. Le ledger
contient repository, executor déclaré, source_revision, build_artifact,
build_digest, started_at, finished_at, run_url et tests. Chaque test possède id
et status PASS, FAIL, ERROR ou SKIP. La requête épingle baseline, source CODE,
case TEST, environment, report, object_id et idempotency_key. AIR contrôle le
commit, le dépôt et les octets retenus du build ; FAIL/ERROR donne FAIL, SKIP donne
INCONCLUSIVE, tous les tests PASS donnent PASS. L'auteur authentifié de l'import
est distinct de l'executor déclaré. Le résultat reste une OperationalEvidence
enregistrée ; la qualification externe signée et indépendante reste séparée.

`effort-calibrate` prend baseline, observations et as_of. Le document retenu
`air.effort-observations/1` fournit des lignes avec id, unit, estimate, activity,
person_days, review_person_days, rework_person_days, ai_used, started_at,
finished_at et source_record. Unités et DeliveryEstimate portent leurs pins
exacts. Revue et reprise sont incluses dans le total. Les activités manquantes,
les fenêtres invalides et l'usage IA mixte restent explicites ; aucun ratio
comparable n'est annoncé pour un périmètre incomplet ou mixte. La concordance
avec une estimation ne démontre pas un gain causé par l'IA.

## Rejouer la réception locale

`scripts/demo_architecture_journey.py --output <nouveau-dossier>` relie le même
dossier aux rôles fictifs fournisseur/consommateur, à un dépôt Git de prototype,
à ses archives de build et aux tests Python exécutés par un runner signé.
Le prix incorrect introduit dans une seconde révision fait échouer le contrat.
AIR expose les preuves impactées et ne reconduit pas l'ancienne réception du
paquet. La présence d'une attestation n'invente aucun avis indépendant.

`scripts/qualify_portfolio_scale.py examples/portfolio-scale-targets.synthetic.json
--output <nouveau-dossier>` conserve les objectifs avant mesure, crée 64 projets
avec 16 révisions chacun, mesure le noyau de stockage et vérifie leurs digests
après restauration. Cette charge synthétique de fondation n'est pas une charge
complète de construction ni une réception de capacité entreprise. Les limites
sont celles du poste et de sa charge de fond pendant la mesure.

Le [protocole UX](ux05-recette-utilisateurs.md) reste à exécuter avec des personnes.
Le modèle `examples/ux-observations.template.json` commence sans séance.
`scripts/check_ux_observations.py <fichier>` exclut les séances synthétiques et
les tâches non exécutées, signale les erreurs critiques et prépare la revue.
Le checker ne certifie ni l'authenticité des observations ni une réception humaine.
