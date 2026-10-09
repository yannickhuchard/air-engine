# Branding des dossiers AIR

Une marque est une configuration de présentation, distincte des révisions
d’architecture. Le projet possède un profil par défaut ; chaque dossier peut
le remplacer entièrement en épinglant sa baseline `{id, revision, digest}`.
Un consultant peut ainsi produire plusieurs dossiers clients dans un même projet,
sans transmettre la marque du premier client au suivant.

Le moteur `air.branding/1` configure `name`, `tagline`, `logo_svg`, `colors`
et `fonts`. Les couleurs reconnues sont `header`, `header_text`, `background`,
`surface`, `text`, `muted`, `link`, `accent`. Les polices sont `body` et `display`.
Voir les trois [profils fictifs](../fixtures/branding/README.md).

## Configurer et générer

Créer une requête `marque.json`, par exemple :

```json
{
  "profile": {
    "name": "Mon entreprise",
    "tagline": "Architecture et transformation",
    "colors": {"header": "#123e55", "link": "#145a74"},
    "fonts": {"body": "Arial", "display": "Georgia"}
  }
}
```

Sur Windows, avec l’API locale démarrée et le fichier de credential protégé :

```powershell
.venv/Scripts/python.exe -m air --home .air branding-configure marque.json --workspace mon-projet --apply
.venv/Scripts/python.exe -m air --home .air deliverables dossier.request.json --workspace mon-projet --apply
```

Le premier appel écrit `branding/brand.json`, `brand.css`, `logo.svg` et
`manifest.json`. Le second réutilise automatiquement `mon-projet/branding/brand.json`,
sauf si sa requête contient déjà `branding`. `--branding chemin.json` choisit
explicitement un profil compilé ou une sélection projet/dossiers. Sans `--apply`,
le CLI fournit un plan. Une régénération identique est idempotente ; les éditions
locales sont protégées par les empreintes de la génération précédente.

Chaque dossier du site possède son propre `branding/` et les pages utilisent ses
styles et son logo. Le nom, les icônes et les couleurs d’installation de la PWA
suivent le **profil du projet** : une installation reste une PWA pour ce projet.
Les changements de styles invalident l’empreinte du cache hors ligne. Les noms
des objets, la légende ontologique, les graphes, les récits et les gates conservent
leurs sources et leurs significations.

## MCP et stockage réutilisable

`air_compile_branding({profile: ...})` renvoie les paramètres normalisés,
empreintes, avertissements et fichiers. Ce calcul ne modifie aucun registre ni
fichier du poste. L’IDE peut appliquer les produits au workspace autorisé.
`air_compile_deliverables` accepte la sélection suivante :

```json
{
  "branding": {
    "default": {"name": "Cabinet conseil"},
    "dossiers": [
      {
        "baseline": {"id": "urn:client:baseline", "revision": 1, "digest": "sha256:…"},
        "profile": {"name": "Client A", "colors": {"header": "#43285e", "link": "#43285e"}}
      }
    ]
  }
}
```

L’empreinte abrégée ci-dessus est illustrative ; utiliser les pins réels du dossier.
Une baseline absente, un mauvais digest ou deux profils pour le même pin sont refusés.
Une marque explicite avec un export partiel `only` ou `website:false` est refusée,
afin de ne pas accepter une configuration qui serait ignorée.

Pour conserver et réutiliser une marque via le MCP, importer un artefact JSON
contenant **exactement** `{"profile": ...}` avec `air_import_artifact`, dans un
namespace où l’identité peut écrire. Le relire avec `air_read_artifact`. Ensuite,
`profile: {"artifact": {"id": ..., "digest": ...}}` peut remplacer un profil
dans le compilateur ou la sélection de livrables. Les droits de lecture et les
deux empreintes, manifeste et contenu, sont vérifiés ; les références d’artefacts
sont conservées dans les paramètres exportés. Aucun choix implicite du dernier
artefact d’un namespace n’est effectué.

Après ajout d’un outil ou paramètre au serveur, rafraîchir le catalogue de la
connexion AIR dans ChatGPT. Un catalogue ancien peut supprimer les paramètres
inconnus avant même que le serveur soit appelé. La correction de publication MCP
conserve la validation URI du serveur et publie une contrainte lexicale compatible
avec les identifiants URN, que certains validateurs de connecteurs interprètent
à tort comme des URL web.

## Importer DESIGN.md

```powershell
.venv/Scripts/python.exe -m air --home .air branding-configure marque.json --design-md client/DESIGN.md --workspace mon-projet --apply
```

Via MCP, fournir le texte dans `profile.design_md`. AIR utilise la
[spécification Google DESIGN.md alpha](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md).
Le document original complet est conservé sous `branding/DESIGN.md` avec son
empreinte. Le frontmatter YAML strict est interprété comme des données ; la prose
et les tokens non mappés ne sont ni exécutés ni appliqués comme instructions.

Les couleurs nommées comme les rôles AIR et `colors.primary` sont reconnues ;
`typography.body` et `typography.display` fournissent leur `fontFamily`.
`design_mapping` permet de choisir explicitement des chemins de tokens :
`{"header":"colors.primary-60","display":"typography.heading-xl"}`.
Les références `{colors.autre}` sont résolues avec détection de cycles et de
valeurs absentes. Les paramètres explicites du profil prennent priorité sur
l’import. Les sections répétées, clés YAML dupliquées, aliases, tags et anchors
sont refusés. Un document uniquement rédigé en prose reste conservé, avec
avertissement et paramètres AIR par défaut.

Il s’agit d’un **import compatible d’un sous-ensemble**, pas d’une conformité
complète à ce format alpha. Les dimensions, composants, élévations et autres
tokens sont conservés dans la source avec avertissement, sans transformation
silencieuse. Les couleurs appliquées acceptent les hexadécimaux RGB à 3 ou 6
chiffres dans DESIGN.md, puis sont normalisées à 6 chiffres ; les autres syntaxes
nécessitent un mapping vers un token RGB pris en charge.

## Périmètre et vérification

Les logos acceptent un SVG inerte borné à 16 Ki caractères, avec `viewBox`, formes,
groupes et texte. Scripts, styles, références externes, images embarquées et
déclarations XML sont refusés. Les formats PNG/JPEG et SVG complexes ne sont pas
pris en charge par ce premier import. Les polices désignent une famille installée
sur le poste avec un repli local ; AIR ne télécharge ni n’embarque de polices.
Les droits du logo et des polices restent ceux de leur fournisseur.

Les paires de texte appliquées doivent atteindre 4,5:1 de contraste, y compris
sur les surfaces claires de lecture AIR. Ce contrôle ne constitue pas une
certification complète d’accessibilité et ne fournit pas un thème sombre intégral.
L’installation Python/SQLite conserve ses dépendances actuelles.

L’atelier BRAG réutilise le nom, logo, couleurs et familles de police du dossier
pour les nouvelles compositions. Pour figer la typographie vidéo sans résolution distante, fournir dans les assets
`BrandBody.ttf` / `BrandBody-LICENSE.txt` et `BrandDisplay.ttf` /
`BrandDisplay-LICENSE.txt`. Sans ces fichiers, le rendu emploie Manrope local
licencié et sa receipt signale explicitement le repli, même si le site utilise
une autre famille installée sur le poste. Les receipts épinglent aussi le branding et son fichier
source ; une marque modifiée rend la finalisation obsolète. Les anciens MP4 restent
préservés et ne deviennent pas des rendus de la nouvelle marque.

Réception du 3 octobre : trois vrais allers-retours d’artefacts via le plugin AIR
connecté dans Codex, puis compilation CLI authentifiée et parité avec un processus
MCP stdio local. Les nouveaux appels directs du plugin attendent le rafraîchissement
du catalogue chargé ; aucune qualification native de l’interface ChatGPT n’est
annoncée. Voir les preuves et limites (document historique ou livrable local non inclus).
