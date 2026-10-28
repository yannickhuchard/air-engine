# Installer AIR directement dans ChatGPT desktop

Ce guide permet de proposer le plugin AIR à ChatGPT desktop depuis un dossier
local, puis de l'utiliser avec le moteur installé sur votre poste. Il concerne
la préversion **Skills-only CLI 0.1.16**, dont les sources se trouvent dans
`plugins/air-local-cli`. Le plugin fournit les skills `air-local-setup` et
`air-local-design` et un helper Python ; le moteur AIR s'installe séparément.

La procédure suit la [documentation officielle OpenAI des marketplaces locales](https://developers.openai.com/plugins/build/plugins#install-a-local-plugin-manually),
consultée le 24 octobre 2026. Une marketplace est ici un catalogue de plugins
qui pointe vers vos fichiers. La disponibilité dépend du client et des règles
de votre espace de travail.

## Avant de commencer

- Utilisez l'application **ChatGPT desktop** avec accès aux plugins locaux et
  à un **chat qui s'exécute localement avec un exécuteur**. Une conversation
  web, mobile ou cloud sans cet exécuteur ne peut pas lancer la CLI de votre poste.
- Téléchargez `air-local-0.1.16-marketplace.zip` et vérifiez son empreinte depuis
  la [release officielle](https://github.com/yannickhuchard/air-plugin/releases/tag/v0.1.16),
  ou utilisez un checkout de cette release contenant `plugins/air-local-cli`.
- Pour les contrôles moteur, prévoyez Python 3.11+, une installation AIR et un
  projet autorisé. SQLite et identité locale sont les valeurs par défaut ;
  Docker, Node, PostgreSQL, OIDC et serveur public ne sont pas nécessaires à AIR.

Choisissez l'une des deux préparations suivantes, puis passez à l'installation
dans l'application. Gardez le dossier choisi à un emplacement stable.

## Option A : vous avez reçu l'archive directe

Vérifiez la provenance et l'empreinte de l'archive à partir du manifeste fourni
par le mainteneur. Extraire l'archive dans un dossier dédié, par exemple
`C:\AIR-plugins` sous Windows ou `~/AIR-plugins` sous macOS. Vous devez obtenir :

```text
AIR-plugins/
  .agents/plugins/marketplace.json
  air-local/plugin.json
  air-local/.codex-plugin/plugin.json
  air-local/skills/air-local-setup/SKILL.md
  air-local/skills/air-local-design/SKILL.md
  INSTALLATION.txt
```

Conservez le dossier `.agents`, qui peut être masqué par l'explorateur. La racine
de la marketplace est `AIR-plugins`, pas son sous-dossier `air-local`.

L'archive simple `air-local-0.1.16-cli.zip` contient uniquement le plugin. Si
vous avez reçu cette archive, extrayez-la puis créez le catalogue décrit dans
l'option B, en remplaçant `./plugins/air-local-cli` par `./air-local`.

## Option B : vous disposez des sources

Depuis le checkout AIR contenant `plugins/air-local-cli`, créez le fichier
`.agents/plugins/marketplace.json` avec ce contenu. Si un catalogue existe déjà,
ajoutez seulement l'entrée AIR à sa liste `plugins`, en conservant les autres
entrées et le nom de la marketplace.

```json
{
  "name": "air-cli-direct",
  "interface": {
    "displayName": "AIR CLI - Distribution directe"
  },
  "plugins": [
    {
      "name": "air-local",
      "source": {
        "source": "local",
        "path": "./plugins/air-local-cli"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

`source.path` est relatif à la racine du checkout, pas à `.agents/plugins`.
Il doit désigner le dossier contenant `plugin.json` et `skills/`.
Ne pointez pas vers `plugins/air-local` : cette autre variante s'appuie sur la
connexion MCP du projet pour les opérations moteur.

## Installer le plugin dans l'application

1. Ouvrez comme projet local le dossier contenant la marketplace : le dossier
   extrait pour l'option A, ou la racine du checkout pour l'option B.
2. Redémarrez ChatGPT desktop pour qu'il découvre le catalogue local.
3. Ouvrez **Plugins**, choisissez la source **AIR CLI - Distribution directe**,
   puis installez **AIR - Architecture Workspace**. Si vous avez conservé un
   catalogue existant, choisissez le nom de cette marketplace.
4. Ouvrez un nouveau chat local dans le projet d'architecture autorisé, avec
   l'exécuteur local disponible. Sélectionnez ou mentionnez le plugin AIR.
5. Lancez son parcours de setup, ou demandez :

   > Utilise le skill air-local-setup pour vérifier les prérequis d'AIR sur ce
   > poste. Le moteur et mon projet sont installés dans les dossiers que je
   > vais t'indiquer. Vérifie les chemins sans afficher les identifiants.

Si vous utilisez déjà la CLI Codex, vous pouvez aussi enregistrer explicitement
la source locale depuis le dossier contenant le catalogue :

```sh
codex plugin marketplace add .
codex plugin marketplace list
```

Cet ajout enregistre la source ; il ne remplace pas l'installation et le setup
dans l'application. Il ne faut pas téléverser le ZIP dans une conversation ni
le soumettre sur le portail développeur pour suivre ce parcours local.

## Préparer le moteur et vérifier la première utilisation

Si le moteur n'est pas installé, demandez explicitement au skill de l'installer
depuis le [dépôt officiel air-engine](https://github.com/yannickhuchard/air-engine),
avec une release identifiée et son empreinte vérifiée. Exemple de demande :

> Installe le moteur AIR officiel pour ce projet sur mon poste, dans un dossier
> dédié, avec SQLite et une identité locale. Examine l'installateur, puis
> démarre le service local et vérifie les prérequis.

Le [guide du moteur](installation.md) détaille l'installation. Depuis les
sources de la version choisie, la commande habituelle est :

```sh
python scripts/install.py --start
```

Le setup doit connaître le chemin du moteur, son home privé, son port et le nom
du fichier d'identité autorisé. La CLI consomme ce fichier protégé ; ne copiez
jamais son contenu dans le chat. Le service reste sur `127.0.0.1`. Aucune
ouverture de pare-feu ni aucun tunnel ne sont requis pour cette variante locale.

Demandez ensuite au skill de vérifier `doctor`, `workstation-check`, `whoami`
et `capabilities` via la CLI, puis de lire la baseline exacte de votre projet.
Faites confirmer la version du moteur, le projet visé et les capacités réellement
disponibles avant de demander des changements. Pour commencer la conception :

> Utilise air-local-design pour m'aider à construire ce projet d'architecture.
> Montre les informations manquantes, pose les questions une par une, puis
> vérifie le modèle avant de générer le site « Projet d'architecture ».

La réussite de ces commandes vérifie la voie CLI. Les applications métier
décrites par le dossier restent à réaliser ultérieurement. Les résultats
locaux transmis au modèle suivent les règles de votre organisation.

## Résoudre les difficultés courantes

| Symptôme | Action |
| --- | --- |
| La source AIR n'apparaît pas | Vérifier le chemin `.agents/plugins/marketplace.json`, le JSON et `source.path`, puis redémarrer l'application. Avec la CLI, consulter `codex plugin marketplace list`. |
| Aucun plugin local ou exécuteur n'est proposé | Vérifier les fonctions disponibles dans votre client desktop et les règles de l'espace de travail avec son administrateur. Le chat web ne remplace pas un exécuteur local. |
| Le skill n'apparaît pas dans le chat | Vérifier l'installation et l'activation du plugin, puis ouvrir un nouveau chat local. Éviter deux variantes AIR actives dans le même chat. |
| `AIR_ENGINE_MISSING` | Indiquer au setup le chemin réel du moteur installé séparément. |
| `AIR_CONFIGURATION_MISSING` | Vérifier le home, le port et l'existence du fichier d'identité choisi, sans afficher de secret. |
| `AIR_EXECUTION_UNAVAILABLE` | Vérifier l'interpréteur Python de l'environnement moteur et l'accès à l'exécuteur local. |
| `AIR_UNREACHABLE` | Vérifier le port et le démarrage du service avec le guide de la version moteur installée. |
| Accès refusé ou capacité absente | Conserver l'erreur et faire vérifier le rôle ou la version ; ne pas changer d'identité ni de moteur automatiquement. |

Après une mise à jour de la source, rafraîchissez la marketplace et redémarrez
l'application, puis vérifiez la version chargée dans un nouveau chat. Avec la
CLI, `codex plugin marketplace upgrade air-cli-direct` rafraîchit la source
enregistrée sous ce nom. Les fichiers du moteur et ses données ne sont pas mis
à jour par l'installation du plugin.

## Disponibilité et portée des vérifications

Au dernier constat du **23 octobre 2026**, la fiche Skills-only 0.1.16 est un
brouillon non soumis : le portail n'accepte plus de nouvelles soumissions
Skills-only à cette date. AIR n'est pas publié dans l'annuaire public OpenAI.
La distribution locale décrite ici en est indépendante. Voir le
[reçu du portail](traceability/directory-public-summary.json).

Le paquet et ses appels CLI ont passé leurs tests locaux. L'installation native,
le setup et le chargement des skills 0.1.16 dans un nouveau chat restent à
valider ; ce guide ne les transforme pas en résultats reçus. Le moteur compagnon est `0.35.0.dev8`. Vérifiez les capacités et permissions
effectivement disponibles avant les fonctions récentes. Consultez [l'état de réalisation](etat-implementation.md).

Références OpenAI consultées le 24 octobre 2026 :
[installation et marketplaces locales](https://developers.openai.com/plugins/build/plugins),
[plugins nécessitant une exécution locale](https://developers.openai.com/plugins/deploy/desktop-only).
