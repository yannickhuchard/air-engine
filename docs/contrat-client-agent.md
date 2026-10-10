# Contexte et catalogue des clients AIR

La [réception locale du 10 octobre](lot-a-consolidation.md) qualifie les
parcours courants Codex 0.159.2 et ChatGPT sur un registre synthétique. Elle
comprend la reprise d’une capsule et les livrables. Dans ChatGPT, rafraîchir
les outils de la connexion existante après redémarrage de l’adaptateur ;
`air_capabilities.engine_version` est le champ de version à lire. Dans Codex,
la recette épingle le MCP local pour éviter de sélectionner un autre registre
via une connexion AIR globale. Les configurations, profils et autorisations
restent explicites ; aucun résultat de ce lot ne vaut réception d’un annuaire.

État du 3 octobre 2026, branche `0.35.0.dev1`. Cette page donne la procédure
courante. La [qualification rc9](perimetre-local-supporte.md) et les preuves P07
restent historiques ; elles ne qualifient pas automatiquement les nouveaux outils.

Avant un travail sur un dossier, lire `air_whoami` et `air_capabilities`, puis
la baseline exacte indiquée par le manifeste du projet. Le nom du plugin ou de
son branding ne permet pas d’identifier le registre connecté. Comparer
`{id, revision, digest}` avec le dossier affiché dans le site. Le même nom de
projet avec une autre empreinte désigne un autre contexte de lecture.

`air_capabilities.client_contract` annonce les empreintes des schémas des
catalogues **supportés**, par profil. Il n’accorde aucun droit et ne décrit pas
à lui seul le catalogue autorisé de la session. Le rôle authentifié et le profil
du serveur restent déterminants ; la politique peut encore limiter les objets.

Les schémas MCP publiés admettent les URN avec une contrainte de schème URI.
Le serveur conserve la validation URI complète. Une erreur de schéma du
connecteur avant l’appel au moteur doit être distinguée d’un refus AIR.
Conserver l’identifiant exact ; ne pas inventer une URL pour contourner ce refus.

## Vérifier un catalogue observé

Enregistrer le véritable résultat `tools/list` du client ou de sa découverte
autorisée, sous cette forme minimale. Ne pas enregistrer les jetons ni les
journaux privés dans le dépôt.

```json
{"tools":[{"name":"air_capabilities","inputSchema":{"type":"object"}}]}
```

Cet exemple incomplet échoue volontairement à la comparaison. Une observation
complète contient tous les noms et schémas réellement découverts, sans les
remplacer par ceux du serveur local. Ajouter éventuellement `expected_baseline`
et `observed_baseline`, chacun avec `id`, `revision` et `digest`, issus du
manifeste et d’une lecture du registre respectivement.

```powershell
python -m air client-contract-check tools-observed.json --profile contribute
```

Choisir le profil réellement autorisé (`read`, `contribute`, `guided` ou `all`).
La commande fonctionne sans home, serveur ou identifiant. Elle compare les
schémas complets, signale les outils absents, supplémentaires ou différents et
le contexte exact éventuel. Un nom de version ou un nombre d’outils identique
ne suffit pas. Code de sortie 2 : divergence ou contexte attendu non confirmé.
Une comparaison réussie reste une comparaison de l’observation fournie ; elle
ne prouve pas une authentification ni une lecture dans le client natif.

Le mode `auto` résout les actions courantes de l’identité, et peut donc différer
d’un profil fixe : un lecteur peut lancer et annuler ses propres calculs privés
avec `air_submit_job` et `air_cancel_job`, absents du profil fixe `read`.
Conserver cette différence dans le diagnostic. Deux outils supplémentaires
autorisés ne constituent pas, à eux seuls, une preuve de catalogue périmé.

Pour les dossiers HTML, vérifier en particulier `air_compile_deliverables` et
ses paramètres `website`, `branding` et `comparisons`. Le branding requiert
`air_compile_branding` dans le profil adéquat. Le profil guidé est volontairement
plus petit ; une fonction absente de ce profil ne démontre pas un cache périmé.

Si le catalogue diverge : recharger la découverte par la fonction disponible
dans le client, puis refaire une lecture avec l’URN exacte et sa révision.
Un processus serveur redémarré ne garantit pas que le client a rechargé son
catalogue. Si le rejet persiste, conserver un reçu expurgé et distinguer un
cache ancien d’une restriction du connecteur, dont la cause doit être confirmée.

## Produire et lire le site

Le compilateur renvoie un plan de fichiers. Un agent disposant d’un shell local
peut l’écrire avec `air deliverables ... --workspace ... --apply`. Un assistant
conversationnel sans shell ne matérialise pas à lui seul le dossier HTML sur le
poste : cette étape passe par la CLI locale ou un opérateur disposant de cet accès.

Chaque dossier HTML offre six parcours : COMEX, managers métier, DSI,
architecture entreprise, architecture solution et réalisation. Les questions
renvoient aux 37 sujets, aux diagrammes et aux objets exacts. Les dimensions
absentes restent signalées, notamment coûts, jalons, RACI et qualité.
La présence de sources ne prouve ni complétude ni approbation. Les contrôles
calculés et leurs actions se lisent séparément des déclarations.

Un parcours par public n’est pas un contrôle d’accès. Tous les fichiers du site
restent disponibles à son destinataire autorisé, y compris les modèles JSON.
La diffusion de cet export doit donc conserver la portée de ses données.

La recette native des nouveautés est distincte des tests locaux. Claude Code,
Claude conversationnel, Codex et ChatGPT doivent être identifiés par leur
surface exacte. Une réussite dans l’un ne qualifie pas les autres.
