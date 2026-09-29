# Provenance et périmètre public

Moteur : 0.34.0rc9, snapshot du code de référence reçu localement. Les sources du
paquet `src/air` sont conservées à l’identique. La distribution ajoute la licence
Apache-2.0, les métadonnées auteur, ce guide et les exemples documentés.
Un chemin local de développeur dans `examples/claude-code.json` devient un exemple
fictif. Le constructeur de release est actualisé pour conserver LICENSE/NOTICE et
exclure le white paper et les workflows CI.

Le dépôt public commence avec un historique neuf. Il n’inclut pas le white paper
original, les reçus de sessions privées, les identifiants, les bases ou l’environnement
du développeur. La sélection initiale utilise une liste de fichiers avec empreintes.
`docs/source-provenance.json` inventorie les sources du moteur et les modifications
de packaging. Les nouveaux reçus publics correspondent aux archives publiques.

Les tests moteur et les données Asteria sont inclus. Les tests des sessions natives,
du plugin distribué séparément et de l’ancien packaging privé sont exclus ; ce n’est
pas la suite complète du dépôt de développement. Aucune nouvelle qualification
native ChatGPT/Codex n’est déduite de l’exécution de ces tests.

## Composants tiers

Le logiciel AIR est sous Apache-2.0 ; les dépendances gardent leurs licences propres.
Les dépendances Python ne sont pas incorporées au wheel AIR : pip les obtient du
registre ou du miroir configuré. `constraints.txt` fixe les versions. Toute
redistribution d’un wheelhouse doit conserver leurs notices et licences.
`docs/dependency-licenses.json` inventorie les métadonnées de licence relevées dans
l’environnement de vérification ; ce n’est pas une concession de licence supplémentaire.

Le schéma OpenAPI de test conserve son attribution et son texte de licence sous
`tests/fixtures/OPENAPI-ATTRIBUTION.md` et `OPENAPI-LICENSE.txt`.
Les présentations peuvent charger Mermaid et les polices IBM Plex depuis des CDN ;
ils ne sont pas inclus dans les archives et ce rendu demande un accès réseau.

Le nom AIR et l’identité de Yannick Huchard indiquent l’origine officielle ; ils ne
constituent pas une certification OpenAI ni une garantie de support contractuel.
