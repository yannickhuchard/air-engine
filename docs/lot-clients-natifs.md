# P07 - Qualification des clients sur poste

**Statut courant : clôture technique locale complète**, vingt cas natifs et six parcours
transversaux reçus. Voir la [clôture et ses preuves](cloture-p07-p08-local.md), avec versions
clientes par cas et gestes opérateur explicites. Validation indépendante et G1 restent
différés. Les étapes ci-dessous conservent l'historique de progression du lot.

**Périmètre courant du 28 septembre 2026 : Codex et ChatGPT uniquement.** Claude n'est
plus requis. La validation indépendante (revue et essai entre postes physiques) est
différée, selon la [décision utilisateur](decision-p07-p08-local.md). Utiliser
`examples/p07-local-reception.template.json` (`air.p07-reception/2`). Les critères
historiques `/1` et leurs preuves restent conservés ci-dessous ; ils ne deviennent
pas des prérequis supplémentaires du nouveau périmètre.

La découverte Codex passe après autorisation explicite de rechercher les outils
différés. Le projet était chargé ; la recette interdisait implicitement la recherche
avant de conclure à tort à un catalogue absent. La nouvelle recette exige les deux
appels natifs réussis, pas seulement la lecture de configuration.

Candidate 0.34.0rc9, SQLite et identité locale. **P07 reste ouvert tant que ses essais natifs
ne sont pas tous exécutés.** Un test de transport, un fichier de configuration ou une réponse
rédigée par un modèle ne remplace pas une trace d'appel du client concerné.

## Parcours disponible

La consolidation courante (document historique ou livrable local non inclus)
épingle les dix cas Codex et sept cas ChatGPT, ainsi que les six parcours transversaux
requis. La reprise dans les deux sens et la parité exacte CLI/API/MCP sont exécutées.
Le contrôle du dossier (document historique ou livrable local non inclus) isole
les trois cas restants : admission sans mandat, annulation/nouveau job et activation
depuis un catalogue périmé côté ChatGPT. Le catalogue natif conserve 62 outils et
n'expose pas encore les trois commandes concernées. Une soumission native de job
est observée ; elle ne vaut pas réception du cycle d'annulation.

Les preuves précisent les adaptations de surface : ChatGPT découvre un registre
AIR neuf par tunnel dans une conversation existante, sans lecture des fichiers du
dépôt ; Codex charge le projet généré. Le scénario de client ancien vérifie un
catalogue devenu périmé après retrait du mandat dans la version testée ; aucune
compatibilité avec toutes les anciennes versions binaires n'est revendiquée.

L'extraction `scripts/p07_chatgpt_evidence.py` associe requête et réponse JSON-RPC,
y compris les identifiants réutilisés après initialisation. Les résultats sont
corrélés aux fenêtres temporelles des tours natifs ; le texte de réponse du modèle
n'est jamais utilisé comme résultat d'outil. Les traces ambiguës ou incomplètes sont
rejetées et les métadonnées privées du client restent hors des rapports publics.

La [recette ChatGPT isolée](p07-recette-chatgpt.md) prépare maintenant le transport
de test avec une identité dédiée et une capture privée des messages. Le profil
contributeur du pilote masque volontairement les engagements ; ce n'est pas une
preuve de refus natif. Les nouveaux résultats Codex (document historique ou livrable local non inclus)
complètent la récupération dans un même thread et la proposition destinée à ChatGPT.
Le [périmètre local publié](perimetre-local-supporte.md) conserve les limites de réception.

1. Installer AIR selon [le skill](../.agents/skills/air-install/SKILL.md), puis vérifier `doctor`
   et `workstation-check`. Aucun abonnement IA n'est nécessaire pour utiliser la CLI AIR.
2. Créer une identité individuelle et son fichier protégé ; accorder seulement les namespaces
   et actions nécessaires. Ne pas partager le fichier de l'administrateur entre architectes.
3. Générer le référentiel et l'adaptateur avec `workspace-init`, puis `ide-setup`, d'abord sans
   `--apply` pour examiner le plan. Claude Code et Codex ont chacun leur adaptateur ; la génération
   n'écrase pas les réglages modifiés ou administrés.
4. Démarrer le client avec le processus MCP déclaré, puis lire `air_whoami` et les versions.
   Lire une baseline exacte avec `air_guide`, préparer avec `air_rebase_drafts`, valider, puis déposer
   explicitement le changement accepté. Une nouvelle session reprend les objets persistants.
5. Pour arrêter un calcul, utiliser `air_cancel_job` avec sa référence exacte. Depuis rc9, le profil
   contributeur expose cet outil ; le service exige toujours d'être le propriétaire du job.
   L'annulation est idempotente. Un calcul annulé reste annulé : une nouvelle demande utilise une
   nouvelle clé, et ne représente pas une reprise silencieuse de l'ancien calcul.
6. Le relecteur utilise sa propre identité et le mandat applicable. Un sous-agent « relecteur »
   portant l'identité de l'auteur ne constitue pas une personne indépendante.

Les secrets restent dans les fichiers privés lus par le processus MCP. Le client reçoit les résultats
d'architecture autorisés, donc son fournisseur IA doit être autorisé à traiter ces données. La recette
livrée emploie exclusivement des données synthétiques et les connexions clientes déjà configurées.

## Recette native reproductible

```sh
python scripts/qualify_native_clients.py --work-root tmp/p07-native --output tmp/p07-native.json
```

`--clients codex` ou `--clients claude-code` limite l'exercice. Le script crée son propre home privé,
ses identités et deux namespaces antagonistes, génère les adaptateurs, puis lance les exécutables
installés avec leur authentification existante. Il n'installe pas les clients, ne change pas leurs
réglages globaux, ne choisit pas un autre modèle et ne désactive pas globalement leurs approbations.
Les étapes demandent seulement des appels AIR explicitement décrits, sur des données fictives.

Les sorties brutes restent privées. Le rapport public ne garde que versions, contrôles booléens,
statuts et empreintes. La lecture des événements distingue un résultat MCP réel, un refus AIR,
une erreur de transport et une simple affirmation du modèle. Un manque de crédits reste un blocage.
L'essai porte sur les CLI non interactives et leur configuration MCP fournie à l'invocation ; il
ne reçoit ni la découverte automatique du projet, ni les interfaces graphiques, ni toutes les versions.
Une approbation interactive exigée par le client reste `CLIENT_APPROVAL_REQUIRED` ; le banc ne la
contourne pas. Sortie 2 si un client est bloqué ou un contrôle échoue, sortie 0 seulement si tous les
contrôles du sous-ensemble exercé passent. Même cette sortie 0 ne reçoit pas l'intégralité de P07.

Le parcours exercé couvre lecture, droits, diagnostic identique à l'API, dépôt, reprise dans une nouvelle
session, source hostile, annulation répétée d'un job, nouveau calcul et lecture après rotation du jeton.
Les créations de job et l'exécution du worker sont pilotées par le banc, pas par le client natif.
Le rapport ne transforme donc pas ce sous-ensemble en succès global IDE-01..IDE-10.

## Réception complète

### Complément exécuté le 27 septembre 2026

Deux recettes supplémentaires sont disponibles depuis le dépôt, sur le moteur rc9 inchangé :

```sh
python scripts/qualify_client_interop.py --work-root tmp/p07-interop --output tmp/p07-interop.json
python scripts/qualify_native_design.py --client codex --work-root tmp/p07-design --output tmp/p07-design.json
```

Utiliser un chemin de sortie neuf : les rapports privés existants ne sont pas écrasés. Les deux recettes
refusent `AIR_DATABASE_URL` et créent uniquement leurs propres installations SQLite temporaires.
La seconde accepte aussi `--client claude-code`, lorsque ce compte peut exécuter des requêtes.

La recette d'interopérabilité a passé **23 contrôles**, avec deux registres et deux identités sur
une même machine. L'export d'une baseline de 24 objets et son diagnostic invalide sont identiques
via CLI, API et processus MCP réel. Le transfert explicite conserve le digest et les dépendances,
reste idempotent et refuse atomiquement un conflit. Une modification dans le registre destinataire
ne se propage pas à l'émetteur. Le même processus MCP refuse les lectures après expiration du jeton,
révocation de politique et arrêt de l'API, puis reprend après remplacement du jeton ou redémarrage.
Cela qualifie ces mécanismes de transport ; ni une deuxième machine physique, ni une session native
ChatGPT/Claude/Codex pendant les interruptions ne sont ainsi reçues.

La recette de design a passé **7 contrôles avec Codex CLI 0.155.0-alpha.9.2** : import d'une révision,
proposition d'un ChangeSet typé, répétition idempotente et lecture de la proposition et de sa baseline
cible dans une nouvelle session. La baseline initiale reste épinglée et immuable ; la proposition
n'est ni approuvée ni publiée. Les arguments sont fournis par la recette et les sources sont vides :
cet essai ne prouve pas la qualité d'une conception libre ni la provenance documentaire d'IDE-03.
La découverte automatique du projet et le changement de famille de client restent à vérifier.

Les preuves complémentaires (document historique ou livrable local non inclus) conservent
les rapports et leurs empreintes. La connexion ChatGPT renvoie maintenant **429** (404 lors de
l'essai du 26 septembre) ; Claude Code refuse encore l'exécution faute de crédits. La suite native
complète attend ces accès, une approbation interactive pour l'annulation et une revue humaine distincte.
**P07 reste IN_PROGRESS.** Ces recettes ne sont pas ajoutées rétroactivement à l'archive rc9 déjà construite.

### Session native Claude Code du 27 septembre 2026

Surface exacte : Claude Code **2.1.281** dans l'application Claude desktop 2.9939.2 (onglet Code),
modèle Claude Opus 5.5, mode de permissions `auto`. Le transport est MCP stdio, déclaré par le
`.mcp.json` du projet, vers l'API locale. Ce n'est pas la CLI 2.1.108 du PATH, dont l'échec de
crédits reste tracé tel quel.

La session a été déplacée dans un dépôt de recette neuf, produit par le même compilateur que `ide-setup`.
Tous les appels AIR ont été faits par les outils MCP de cette session.

```sh
python scripts/p07_session_bench.py --root tmp/<banc> prepare --client claude-code
python scripts/p07_session_bench.py --root tmp/<banc> act <geste>
python scripts/p07_session_evidence.py --root tmp/<banc> --transcript <journal> --since <UTC> --tested-revision <commit> --output tmp/<banc>/evidence-N
```

**Rôle des deux scripts**
- Le banc crée un home privé `.air-p07` avec SQLite, une identité éditeur dédiée et les données synthétiques.
- Il exécute seulement les gestes d'opérateur : politique, expiration, révocation et rotation du jeton,
  coupure et redémarrage de l'API, worker, ajout d'un second client. Il refuse `AIR_DATABASE_URL`, un
  autre home et toute autre base que la sienne.
- L'assemblage lit les appels MCP réellement terminés dans le journal du client, jamais la prose du modèle.
  Il les découpe par geste, recalcule la parité API/CLI et les faits du registre, puis produit le dossier.

**Cas IDE**
- PASS pour IDE-01, 02, 03, 04, 06, 08 et 09.
- **PARTIAL** pour IDE-05 : l'admission n'est ni publiée par le serveur, ni présente côté client, mais
  aucun refus au moment d'un appel n'est atteignable.
- **PARTIAL** pour IDE-07 : Claude → Codex est vérifié, Codex → Claude n'est pas exécuté.
- **PARTIAL** pour IDE-10 : l'écriture via un catalogue périmé est refusée, l'activation n'est pas tentée.

**Parcours et dossier**
- Expiration et rotation passent dans le même processus MCP.
- La coupure de l'API a révélé un défaut : le client recevait `AIR_FORBIDDEN` 403 au lieu d'une
  indisponibilité. Il est corrigé (`AIR_UNREACHABLE`), mais pas encore requalifié dans Claude, car le
  processus MCP de la session date d'avant la correction.
- Le dossier assemblé reste **INCOMPLETE** : il manque ChatGPT, le rapport Codex complet, la revue humaine
  et le second poste physique.

**Reprise Claude → Codex**
- Codex a relu le ChangeSet et la baseline candidate aux empreintes exactes, avec l'identité distincte
  `p07-session-codex` et sans transfert de conversation.
- Il a chargé l'adaptateur corrigé, par un MCP fourni à l'invocation.

Preuves expurgées (document historique ou livrable local non inclus),
[passation Codex](p07-reprise-codex.md).

### Complément natif sur l'adaptateur corrigé

Les preuves complémentaires (document historique ou livrable local non inclus) portent
sur le moteur de `86608ca`, distinct de celui de la session initiale ci-dessus. Elles ne réécrivent
ni ses sept cas reçus, ni ses échecs, et ne constituent pas une suite complète sur cette nouvelle source.

- Une nouvelle session Claude Desktop Code charge la configuration du projet déjà approuvé.
  Ses instructions AIR sont présentes et ses appels natifs fonctionnent.
- Pendant l'arrêt de l'API, `air_get` et `air_whoami` renvoient `AIR_UNREACHABLE`, sans objet.
  La même session retrouve son identité et le même digest après redémarrage.
- Codex dépose une proposition typée que Claude reprend avec une identité distincte, aux digests
  exacts, sans recevoir la conversation productrice. La provenance déclarée correspond au producteur ;
  aucune approbation ni publication n'en découle.
- Codex découvre temporairement les outils d'admission/activation du banc synthétique. Après
  révocation opérateur, ses deux appels natifs sont refusés 403. Les droits initiaux sont restaurés
  et aucune réservation, autorisation, activation ou admission n'est créée. Cela couvre un catalogue
  client conservé après révocation, pas la compatibilité d'un ancien binaire client.

Les recettes sont `p07_native_handoff.py`, `p07_native_stale_catalog.py` et `p07_native_discovery.py`
dans `scripts/` ; chacune prend `--root tmp/<banc>` et `--output tmp/<sortie-neuve>`.
La première prépare le travail Codex à reprendre réellement dans Claude ; elle ne déclare pas
elle-même cette reprise exécutée. La seconde modifie uniquement la politique du banc isolé et
la restaure dans `finally`. La troisième n'ajoute aucune configuration MCP à l'invocation et
ne modifie pas la confiance du projet ni les réglages globaux.

La première tentative de reprise a révélé une provenance copiée de Claude dans la fixture Codex.
La suivante a été refusée 422 pour changement d'identité dans un REPLACE. Ces tentatives restent
conservées ; la recette corrigée produit une nouvelle révision et un ChangeSet distinct.

La découverte automatique Codex reste **INCOMPLETE** : le client n'utilise pas le MCP local généré.
Son premier essai appelle le connecteur distant `codex_apps`, qui répond 404 ; cette réponse ne
prouve aucune découverte locale. Le MCP fourni explicitement à l'invocation fonctionne.
Un second essai interdisant explicitement ce connecteur distant ne produit aucun appel AIR local.
La cause de cette différence n'est pas établie. Aucun réglage global ni garde d'approbation
n'est modifié pour transformer l'essai en succès.

`p07_followup_evidence.py` assemble les observations natives, vérifie les empreintes des journaux,
contrôle la source moteur et conserve une copie privée figée du journal Claude. Les journaux et
identifiants secrets restent hors du dépôt ; seul le résumé expurgé est versionné.
Les empreintes des fichiers réellement testés et celles du commit en LF sont distinctes et
conservées : trois fichiers du checkout avaient déjà des fins de ligne CRLF. Le contenu comparé
en LF correspond au commit ; aucune empreinte historique n'est remplacée.
Les 25 tests locaux de recettes, banc, extraction des appels et vérificateur de dossier passent.
Les refus natifs Claude IDE-05/10, les suites complètes sur la même source, l'annulation interactive
Codex, ChatGPT, le second poste physique et la revue humaine indépendante restent à recevoir.

### Diagnostic de découverte et complément du 28 septembre

La preuve du 28 septembre (document historique ou livrable local non inclus) identifie la
cause des essais Codex précédents : `config/read` désactive la couche de projet avec une demande
explicite de confiance pour le dépôt imbriqué `workspace-codex`. Le précontrôle ajouté à
`p07_native_discovery.py` utilise `scripts/p07_codex_config.py` : protocole natif en lecture seule,
délai borné, arrêt du processus de diagnostic, aucun changement de confiance ni publication de
configuration privée. Un client incompatible, un délai dépassé ou une couche absente conserve
`INCOMPLETE`. Si la couche est désactivée, aucun essai au modèle n'est lancé.

Le propriétaire du poste doit approuver ce dépôt dans son client, puis relancer la recette vers une
sortie neuve. La documentation officielle confirme que les couches de projet sont réservées aux
[projets approuvés](https://learn.chatgpt.com/docs/config-file/config-basic). Ce diagnostic ne vaut
ni découverte des outils, ni réussite des appels ; la recette les vérifie seulement après ce précontrôle.

Dans la session Claude existante sur le moteur corrigé, dix contrôles supplémentaires passent :
soumission native, double annulation idempotente, répétition de la clé annulée sans redémarrage,
nouvelle clé produisant un autre job, lecture finale de l'ancien `CANCELLED` à zéro tentative et du
nouveau `SUCCEEDED` sans réservation, identité conservée et source hostile sans élévation.
Le diagnostic `AIR_REFERENCE_MISSING` obtenu par Claude est identique à ceux de l'API et de la CLI.
Le banc exécute le worker et contrôle l'absence d'engagement ; ces gestes ne sont pas attribués au client.
Le script `p07_claude_job_evidence.py` recalcule ces faits depuis les appels natifs, fige le journal
privé et ne compte pas un job simplement en file d'attente comme un calcul terminé.

32 tests locaux passent ; aucune CI. Ces pièces complètent IDE-04/06/09 sur le moteur corrigé,
sans recevoir les suites natives manquantes ni P07. Le connecteur distant reste indisponible (404).

### Dossier et critères de clôture

Le [modèle de dossier](../examples/p07-reception.template.json) exige **ChatGPT, Claude Code et Codex
séparément**, les dix critères [IDE-01..IDE-10](integrations-ide.md#4-suite-de-qualification-commune),
et les parcours transversaux : identités, revue indépendante, coupure/reprise, expiration, rotation,
changement de client, échange explicite entre postes et parité CLI/API/MCP.

```sh
python -m air client-reception-check dossier-p07.json
```

Chaque référence est `{ "path": "rapport.json", "sha256": "<64 caractères hexadécimaux>" }`, relative
au dossier. Liens, échappement de répertoire, empreinte incorrecte, document de plus de 1 Mio ou JSON
ambigu sont refusés. Un rapport client suit `air.native-client-reception/1` et comporte `client`,
`client_version`, `surface`, `os`, `transport`, `execution_kind: NATIVE_CLIENT`, `air_version`,
`source_sha256` et `cases`. Chaque cas contient `status` et une référence `evidence`.
Les modèles [client](../examples/p07-native-client.template.json) et
[cas](../examples/p07-native-case.template.json) restent volontairement non exécutés.

Une preuve de cas donne `case`, `client`, `client_version`, `execution_kind: NATIVE_CLIENT`,
`air_version`, `source_sha256`, `transcript_sha256`, des `observations` expurgées et
`expected_only: false`. Une preuve transversale donne `journey`, `status`, `air_version`,
`source_sha256`, `transcript_sha256` et `expected_only: false`. La revue exige aussi des identités
distinctes `author_identity` et `reviewer_identity`, et `human_review_performed: true`.
Ne renseigner ces éléments qu'après l'exécution et la revue réelles, jamais à partir d'un oracle.

Sortie 2 : `INCOMPLETE`, avec lacunes ; sortie 0 : `READY_FOR_INDEPENDENT_REVIEW`. Même dans ce second
cas, le vérificateur ne signe rien : `p07_received`, `authorship_verified`,
`organizational_independence_verified` et `production_ready` restent faux. Il contrôle la cohérence
du dossier, pas l'authenticité de fichiers produits hors d'AIR ni l'identité humaine derrière un compte.

## ChatGPT et autres surfaces

ChatGPT web nécessite une connexion joignable depuis son environnement ; une URL `localhost` sur le PC
ne suffit pas. Le tunnel AIR existant a déjà été essayé historiquement, mais doit fonctionner et être
requalifié sur cette candidate avec une identité dédiée. Un compte de tunnel partagé ne devient pas
un SSO individuel. Une connexion indisponible n'autorise pas à annoncer un succès ChatGPT à partir de Codex.

Les clients locaux Codex documentent stdio et Streamable HTTP ainsi qu'une configuration de projet
approuvé : [documentation OpenAI](https://developers.openai.com/codex/mcp).
Claude Code dispose du mode non interactif et d'une configuration MCP propre :
[référence CLI](https://code.claude.com/docs/en/cli-reference), [MCP](https://code.claude.com/docs/en/mcp).
Les options effectivement utilisées sont vérifiées sur l'aide des exécutables installés ; une option
documentée d'une version plus récente n'est pas supposée présente sur celle du poste.

Claude.ai, Copilot, Gemini CLI, Antigravity et OpenCode restent non qualifiés tant que leurs propres
parcours ne sont pas exécutés. La CLI AIR demeure le repli local. Aucun serveur central ni aucune
synchronisation automatique entre registres ne sont nécessaires ou revendiqués ici.
