# Plugin AIR - Architecture Workspace

**AIR - Architecture Workspace 0.1.4** est le plugin officiel du projet AIR, développé par
**Yannick Huchard**. Source publique du plugin : https://github.com/yannickhuchard/air-plugin.
Les manifestes déclarent `author.name: Yannick Huchard` et
`interface.developerName: Yannick Huchard`, avec le lien vers son profil GitHub.
Il n'existe pas de certification implicite OpenAI/Anthropic, d'adresse de support
inventée. La licence **Apache-2.0** est confirmée par le titulaire des droits le
28 septembre 2026 ; le paquet conserve `LICENSE` et `NOTICE`.

Le nom affiché précise l’usage d’architecture ; l’identifiant `air-local` reste stable.
Le logo bleu nuit et turquoise est inclus dans `assets/logo.png` et déclaré dans
le manifeste Codex. Il est créé pour AIR avec assistance générative.

## Ce qui est livré

Le dossier [plugins/air-local](../plugins/air-local/README.md) contient :

- un manifeste portable `plugin.json` et le manifeste de compatibilité Codex ;
- `air-local-setup`, pour installer le moteur et connecter le référentiel ;
- `air-local-design`, pour concevoir, vérifier, simuler et produire les livrables ;
- une référence sur les connexions par projet et les installations freelance.

Ce paquet de skills réutilise le moteur et ses générateurs `workspace-init` et
`ide-setup`. Il ne contient pas de serveur MCP global : chaque référentiel conserve
sa configuration, son home et son identité. Les mises à jour du plugin ne touchent
pas les bases. Python, SQLite et l'authentification locale restent suffisants pour
le profil initial ; aucun hosting central AIR n'est requis.

## Construire et installer

Depuis le dépôt, avec Python 3.11+ (aucune dépendance supplémentaire) :

```text
python scripts/build_plugin.py --output-dir dist/plugin
```

L'archive `air-local-0.1.4.zip` contient un dossier `air-local` ;
`plugin-package.json` donne son SHA-256 et celui de chaque fichier. Le constructeur
utilise une liste explicite de neuf fichiers publics, normalise les fins de ligne des textes
et fixe les métadonnées ZIP. Les octets PNG du logo sont conservés à l’identique. Les fichiers privés adjacents ne sont pas incorporés.
Comparer l'empreinte avec un manifeste obtenu de la source approuvée : le hash
seul ne constitue pas une signature de l'auteur.

Pour une installation Codex, extraire le dossier dans `~/plugins/air-local`, puis
demander au skill Plugin Creator de l'inscrire dans la marketplace personnelle
`~/.agents/plugins/marketplace.json`, en préservant les entrées existantes. Il doit
pointer vers `./plugins/air-local`, catégorie Productivity, installation AVAILABLE
et authentification ON_INSTALL. Installer avec `codex plugin add air-local@personal`
si la marketplace s'appelle `personal`, ou depuis l'interface de l'application.
Ne pas remplacer un dossier déjà personnalisé sans examiner ses différences.

Ouvrir une nouvelle conversation et demander : « Utilise AIR Local pour connecter
le référentiel de cette entreprise ». Le skill lit les instructions d'installation
du moteur choisi, puis utilise les générateurs AIR. Pour un moteur neuf, le parcours
habituel est `python scripts/install.py --start` depuis son dépôt officiel.

Sur le poste de développement, la version 0.1.0 a été enregistrée dans la marketplace
personnelle et installée avec succès par la CLI Codex. Les versions 0.1.1 et 0.1.2 sont empaquetées
et leurs manifestes sont validés ; aucune réinstallation native de cette révision
de licence n'est annoncée. Les fichiers de marketplace
et de cache restent hors du dépôt. Le chargement effectif des skills dans une
nouvelle conversation n'a pas encore fait l'objet d'une recette native dédiée.

## Compatibilité et données

Le format portable est fourni conformément à la
[documentation des paquets de plugins](https://developers.openai.com/plugins/build/plugins).
L'installation CLI Codex a été vérifiée. La compatibilité native avec chaque autre
IDE reste à qualifier ; les adaptateurs déjà livrés par AIR conservent leur périmètre.

ChatGPT nécessite une connexion MCP distante propre à l'installation (tunnel sécurisé
ou endpoint autorisé). La distribution de ces skills n'enregistre pas cette connexion,
ne copie aucun tunnel et ne résout pas automatiquement un catalogue obsolète. Le
stockage local n'empêche pas l'envoi des données sélectionnées au fournisseur du
modèle. L'entreprise conserve la décision sur les données qu'elle autorise à partager.

Ce plugin ne synchronise pas les entreprises. Son paquet est public sur GitHub ;
il reste absent de l’annuaire officiel OpenAI. Le moteur associé reste la candidate 0.34.0rc9 ; P07, P08 et G1 conservent
leurs statuts dans le [périmètre local](perimetre-local-supporte.md). La
preuve du paquet (document historique ou livrable local non inclus) distingue installation,
tests locaux et qualifications encore non exécutées. Aucune CI n'a été lancée.

## Publication et référencement

La [version 0.1.4](https://github.com/yannickhuchard/air-plugin/releases/tag/air-local-v0.1.4)
est publiée avec le [moteur public rc9](https://github.com/yannickhuchard/air-engine).
Le skill d’installation pointe vers cette distribution et les trois dossiers Asteria.
Le reçu courant (document historique ou livrable local non inclus) vérifie paquet et téléchargement.
Les [résultats et limites](distribution-publique-livree.md) distinguent distribution
locale reçue et annuaire ChatGPT encore non soumis.

### Historique du 28 septembre

La [préversion publique 0.1.3](https://github.com/yannickhuchard/air-plugin/releases/tag/air-local-v0.1.3)
est publiée dans le dépôt séparé [air-plugin](https://github.com/yannickhuchard/air-plugin),
avec ZIP, manifeste SHA-256 et logo. Le téléchargement anonyme et les neuf fichiers
ont été vérifiés. Le dépôt du moteur `yannickhuchard/air` reste privé, avec son historique.
Le reçu 0.1.3 (document historique ou livrable local non inclus) conserve les preuves.
La publication privée [0.1.2](https://github.com/yannickhuchard/air/releases/tag/air-local-v0.1.2)
et son reçu restent historiques.

La marketplace Git publique est enregistrée dans Codex sous `air-official` :

```text
codex plugin marketplace add yannickhuchard/air-plugin --ref main
codex plugin add air-local@air-official
```

L’enregistrement de la marketplace a été vérifié ; la réinstallation native de
0.1.3 et sa qualification dans une nouvelle conversation ne sont pas revendiquées.

**Soumission OpenAI : NOT_SUBMITTED.** Le portail est ouvert mais attend une
connexion au compte développeur. Les pages publiques de confidentialité, conditions,
support, métadonnées et huit scénarios de revue sont préparées dans
[submission](https://github.com/yannickhuchard/air-plugin/tree/main/submission).
Ces scénarios ne sont pas des résultats d’exécution. L’identité, les pays de
publication et la connexion ChatGPT de revue restent à établir ; les sources du
moteur et les données synthétiques sont désormais publiques.

La distribution GitHub et le référencement officiel sont distincts. La
[procédure OpenAI](https://developers.openai.com/plugins/deploy/submission)
prévoit identité vérifiée, soumission, revue puis publication après approbation.
Le [guide de migration](https://developers.openai.com/plugins/guides/submit-claude-plugin)
demande une revue spécifique pour les workflows dont le fonctionnement central
nécessite une exécution locale. AIR dépend d’un moteur local et d’une connexion MCP
configurée séparément : la voie « Skills only » ne suffit pas à démontrer son
éligibilité. Aucun tunnel de développeur ni serveur partagé n’est publié.

Le moteur reste une dépendance séparée, désormais disponible publiquement sur
[air-engine](https://github.com/yannickhuchard/air-engine). Le dépôt de développement
original conserve son historique privé. La disponibilité du code ne remplace pas
l’acceptation du mode de connexion par OpenAI.
