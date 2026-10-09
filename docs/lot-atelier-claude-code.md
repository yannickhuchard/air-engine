# Référentiel d’entreprise et atelier Claude Code - tranche 28

Deux contrats de service expérimentaux intégrés et en cours de qualification : air.workspace/0.28 compile un
référentiel d’architecture de solution à l’échelle d’une entreprise, air.ide-adapter/0.28 compile les fichiers
d’un client agentique pour ce référentiel. Aucun des deux n’ajoute de type persistable ni de table SQL. Ils
répondent aux travaux L03.1/L03.2 et L05.2 ; `resolve`, le lockfile, les douze skills prévus et la matrice de
compatibilité complète restent à construire.

## Référentiel - air.workspace/0.28

La requête déclare l’organisation (nom, préfixe d’URN, préfixe de namespace), le dépôt, un à soixante-quatre
domaines et les profils visés. Chaque domaine porte un code, un titre, une finalité, un namespace et un segment
d’URN. Codes, namespaces et segments sont uniques ; chaque namespace commence par le préfixe de l’organisation.
Un profil inconnu est refusé.

Le produit est une arborescence de huit fichiers communs - `air-workspace.json`, `air-workspace.request.json`,
`docs/conventions-referentiel.md`, `README.md`, `AGENTS.md`, `.gitignore`,
`policies/namespace-policy.example.json`, `.github/workflows/air-check.yml` - et de trois fichiers par domaine :
`domains/<code>/dossier.json`, `domains/<code>/README.md` et `domains/<code>/drafts/README.md`. Les identifiants
conventionnels dérivent du manifeste : `urn:air:<préfixe>:<segment>` pour la base, puis `:scope`, `:baseline` et
`:changeset`. Soixante-quatre domaines tiennent dans les bornes, soit 199 fichiers et environ 117 KiB.

`air-workspace.request.json` conserve la requête exacte : ajouter un domaine consiste à l’éditer puis à relancer
`workspace-init … --apply --replace-generated`. Les fichiers qui dérivent de la liste des domaines - conventions,
dossiers, exemple de politique et workflow de contrôle - sont régénérés ; `README.md` et `AGENTS.md` appartiennent
au dépôt et ne citent donc aucun domaine, pour ne pas devenir faux au domaine suivant.

Le `README.md` de chaque répertoire de brouillons contient un squelette de Scope typé, valide au sens du moteur,
avec des dates de remplissage explicites. Il est dans un bloc de documentation, jamais dans un fichier déposable.

Le workflow de contrôle produit ne crée aucune admission. Son étape d’installation d’AIR est à compléter par
l’entreprise ; tant qu’elle ne l’est pas, la validation des brouillons s’annonce en avertissement et la CI reste
verte plutôt que rouge par construction.

Le rapport indique, pour chaque domaine, la politique d’accès **effective du sujet authentifié à cet instant**
(`current_policy.read` et `current_policy.write`) et l’empreinte de la politique lue. C’est une lecture, pas
une attribution : aucun droit n’est créé et aucune politique n’est installée. Le registre n’est ni lu ni écrit
par la compilation ; deux appelants autorisés obtiennent les mêmes octets.

La politique d’exemple ne contient aucun sujet et n’est pas installable en l’état : une politique chargée sans
sujets refuse tout accès nommé. Elle doit être complétée puis installée explicitement avec `policy-set`, sous
revue. Les noms de fichiers du référentiel sont fixés par ce contrat expérimental ; la décision L00 sur les noms
normatifs d’un dépôt solution-air reste ouverte.

## Adaptateur - air.ide-adapter/0.28

La requête déclare le client (`claude-code` uniquement), le dépôt, le serveur et le niveau d’accès. Le serveur
est décrit par un interpréteur et une racine AIR en chemins absolus, un nom de fichier d’identifiant sans
séparateur, un port et, pour un serveur d’équipe, une origine et une autorité de certification. Une origine
porteuse d’identifiants, de requête ou de fragment est refusée ; HTTP simple n’est accepté que sur la boucle
locale. Le champ facultatif `shared_instructions` désigne les instructions communes du dépôt : quand il est
présent, la section générée y renvoie au lieu de les répéter.

Le produit contient `.mcp.json`, `CLAUDE.md`, `.claude/settings.json`, `.claude/air-adapter.json`, un skill,
trois commandes et un sous-agent de relecture. `.claude/air-adapter.json` conserve version, empreinte de source,
empreinte du générateur, description de surface et empreinte de chaque fichier ; les fichiers Markdown la portent
aussi en commentaire. Les deux fichiers de configuration du client ne portent pas d’empreinte interne pour garder
leur schéma lisible par le client. L’empreinte de source porte sur les entrées normalisées - client, dépôt,
commande de serveur, niveau d’accès et instructions communes - et non sur la forme littérale de la requête.

Les en-têtes produits sont des scalaires YAML entre guillemets et les listes d’outils des tableaux JSON ; le skill,
les commandes de lecture et le sous-agent reçoivent aussi `Read`, `Glob` et `Grep`, sans quoi ils ne pourraient pas
ouvrir les fichiers que leur propre texte leur demande de lire. Le contenu du skill et de la commande de
proposition suit le niveau d’accès : en `read-only`, ils demandent de préparer le lot et de le remettre à un
contributeur habilité au lieu de tenter un dépôt qui serait refusé.

`.claude/settings.json` est un fichier généré : un changement de niveau d’accès doit pouvoir corriger les
permissions. Les préférences locales vont dans `.claude/settings.local.json`, qu’AIR ne produit ni ne lit. La
liste de refus vise aussi la racine AIR déclarée, les fichiers d’identifiants et `.mcp.json`.

Le niveau `read-only` autorise les trente-quatre outils MCP en lecture. Le niveau `contribute` ajoute onze
outils de contribution de conception. Les seize outils engageants - admission, activation, renouvellement,
clôture, publication et révocation de package, offres de capacité, annulation de job - sont refusés par la
configuration dans les deux cas. Un test vérifie que cette partition couvre exactement le catalogue MCP courant.

Aucun jeton n’est lu, généré ou écrit : le processus MCP lit lui-même le fichier protégé désigné par son nom.
Les fichiers produits sont contrôlés et refusés s’ils contiennent une chaîne ressemblant à un jeton.

## Zones, plan et écritures

Chaque fichier porte une zone. `GENERATED` appartient à AIR : `air-workspace.json`, la requête conservée, les
conventions, les dossiers de domaine, l’exemple de politique, le workflow de contrôle et tous les fichiers du
client. `SEEDED` est déposé une fois puis appartient au dépôt : `README.md`, `AGENTS.md`, `.gitignore` et les
README de domaine et de brouillons. `MARKED_SECTION` délimite la part d’AIR de `CLAUDE.md` entre
`<!-- air:generated:begin -->` et `<!-- air:generated:end -->` ; le reste du fichier n’est jamais touché.

Avant toute écriture, chaque fichier est revérifié : chemin, taille et empreinte du contenu, confinement dans le
répertoire de destination, refus des liens symboliques. Une réponse de serveur n’est pas réputée sûre parce
qu’elle s’est décodée.

La CLI calcule un plan avant d’écrire : `CREATE`, `UNCHANGED`, `PRESERVED`, `SECTION_UPDATE`, `SECTION_MISSING`
ou `CONFLICT`, avec un diff unifié tronqué à 200 lignes. Sans `--apply`, rien n’est écrit. Avec `--apply`, les
fichiers absents sont créés et les sections marquées rafraîchies ; un fichier `SEEDED` existant est conservé et
un fichier `GENERATED` divergent est refusé. `--replace-generated` réécrit ces derniers, jamais un fichier
`SEEDED` ni une ligne hors section marquée. Un chemin sortant du répertoire de destination est refusé. Le code
de sortie vaut 1 s’il reste un `CONFLICT` ou un `SECTION_MISSING`, 0 sinon ; réexécuter la commande ne détruit
pas le travail local.

Les fichiers sont bornés à 64 KiB chacun et 512 KiB par ensemble ; requête et rapport partagent le budget
d’un MiB des autres services.

## Limites visibles

Ces services produisent des fichiers. Ils n’accordent aucun droit, n’installent aucune politique, ne créent
aucun objet, baseline, réservation ou revue, et ne contactent aucun serveur. Une règle de permission cliente
peut être ignorée ou modifiée localement sans qu’AIR le sache : seules les autorisations du serveur sont
effectives, et elles sont réévaluées à chaque appel.

L’état de support déclaré est `ADAPTER_DELIVERED` dans la matrice « documenté / adaptateur livré / testé /
supporté ». `client_qualified` reste faux : la recette démarre le processus déclaré par la configuration
générée et complète une session MCP, mais elle n’exécute pas le client Claude Code lui-même. Les autres
familles d’IDE ne sont pas implémentées. La suite IDE-01 à IDE-10 n’est pas exécutée.

Les contenus générés sont rédigés en français ; aucune autre langue n’est implémentée. Les conventions
produites ne prouvent ni la conformité AIR, ni la réception d’un dossier, ni la qualité d’une conception.

## Accès et recette

`workspace-init` / `POST /v1/workspaces/compile` / `air_compile_workspace` et `ide-setup` /
`POST /v1/ide/adapters` / `air_compile_ide_adapter` partagent le même calcul ; le catalogue MCP compte
soixante et un outils. Les deux commandes CLI exigent `--workspace` et acceptent `--apply` et
`--replace-generated`.

La recette `scripts/demo_atelier.py` compile le référentiel des quatre domaines Asteria et son adaptateur,
compare CLI, API et MCP, écrit l’arborescence, la réapplique sans changement, puis **démarre le processus
exactement déclaré par le `.mcp.json` produit**, sans modifier un seul de ses arguments, et complète
`initialize` puis `tools/list` sur soixante et un outils. Elle vérifie ensuite que les objets des trois
baselines de 88 objets ne portent que le namespace déclaré de leur domaine ou celui du socle partagé, qu’un
sujet restreint voit sa politique réelle domaine par domaine, qu’une note locale ajoutée sous la section marquée
et un `README.md` réécrit par l’équipe survivent à une régénération avec `--replace-generated`, qu’un fichier
`GENERATED` divergent est refusé avec un code de sortie 1, et que les produits sont identiques après
restauration. Elle n’exécute pas le client Claude Code et ne passe pas la suite IDE-01 à IDE-10.
