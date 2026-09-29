# Connexion des agents et dossiers

Installer le [plugin officiel](https://github.com/yannickhuchard/air-plugin).
Le moteur de ce dépôt est sa dépendance séparée. Le plugin et le moteur n’ont pas
le même numéro de version.

Pour un IDE local, créer une identité limitée avec `air --home <home> token-create
--subject architecte --role reader --name architecte.json` puis configurer un MCP stdio :

```text
<python-de-la-venv> -m air.mcp --home <home-absolu> --credential architecte.json --access read
```

Le processus lit le fichier protégé ; ne pas insérer son contenu dans la configuration.
La lecture ne permet pas d’écrire. Pour contribuer, attribuer explicitement le rôle,
les namespaces et les permissions nécessaires puis choisir le profil adapté.
Un profil MCP ne permet pas de dépasser les droits côté serveur.
`air workspace-init` et `air ide-setup` produisent le référentiel et sa configuration ;
consulter leur aide et les requêtes exemples avant application.

Pour ChatGPT, suivre le [statut de connexion public](https://github.com/yannickhuchard/air-plugin/blob/main/DISTRIBUTION.md).
Le chemin MCP local n’est pas une URL distante. La publication dans l’annuaire et
la connexion par installation ne sont pas reçues. Ne pas publier un jeton ou un tunnel
de développement comme point d’accès commun à tous les architectes.

Prompts utiles une fois le référentiel effectivement connecté :

- « Lis la baseline de mon dossier SAV et explique les informations qui manquent. »
- « Prépare une variante de l’architecture ; montre le diff et ses impacts avant dépôt. »
- « Vérifie les contraintes et simule les scénarios disponibles, en gardant visibles les inconnues. »
- « Prépare les livrables pour les ingénieurs, le chef de projet et les opérations. »

Les exemples sous `fixtures` sont des données à importer dans un registre isolé,
pas des registres déjà connectés. La recette Asteria crée et arrête sa propre instance.
Les objets et baselines persistés, pas l’historique du chat, constituent le dossier.
