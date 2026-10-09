# Compilation OpenAPI - tranche 27

Contrat de service expérimental air.openapi-compiler/0.27 réceptionné dans ce sous-périmètre ; voir la preuve de réception (document historique ou livrable local non inclus). Il utilise les baselines et TechnicalBinding du profil architecture/0.26 sans ajouter de type normatif persistable ni de table SQL. CompilationProfile, ImplementationArtifact et ExecutableArchitectureModel restent à implémenter dans leurs propres contrats.

## Entrées et produit

La requête épingle baseline et binding, et fournit titre/version du document. Toute la baseline doit être lisible. Chaque DataSchema est chargé depuis son manifeste local autorisé ; descripteur, empreinte, MIME et éventuelles gardes du contexte source sont vérifiés. Le compilateur réutilise le sous-ensemble JSON plat air.flat-json/0.23 et refuse les schémas distants ou non pris en charge.

Le résultat contient une description [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html), des composants de schéma, les chemins et opérations déclarés, corps de requête explicitement obligatoire ou facultatif, réponse déclarée et éventuel endpoint. Les références entre composants sont locales. Aucun endpoint n’est contacté.

Les nombres Decimal restent exacts : aucun passage par float. La sérialisation trie les clés, conserve les nombres décimaux et termine par LF ; elle ne revendique pas JCS. content_digest porte sur les octets UTF-8. Le rapport conserve aussi l’empreinte de requête, celle du rapport, les mappings JSON Pointer vers objets exacts et les manifestes/empreintes des schémas.

## Limites visibles

Le document est marqué DRAFT_DESIGN_ONLY. Les mécanismes de sécurité ne sont pas générés depuis le texte des contrôles ; les comportements, effets, pré/postconditions et erreurs métier ne sont pas implémentés. Les correspondances sémantiques avec les DataEntity représentées ne sont pas qualifiées par cette compilation. Les pertes figurent dans le rapport et dans une extension du document. Les opérations absentes du mapping sont listées explicitement.

Le générateur conserve versions et empreintes des composants observés au démarrage du module ; ce n’est pas une signature. La reproduction suppose cette même chaîne de génération. Le service retourne un produit et ne crée pas encore un ImplementationArtifact géré ou une capture historique de compilation.

Les schémas chargés sont bornés au total à 1 MiB, la sortie à 512 KiB et le rapport à 1 MiB. Aucun nouveau paquet ou service n’est obligatoire pour l’installation AIR.

## Accès et recette

openapi-compile / POST /v1/compilations/openapi / air_compile_openapi partagent le même calcul. La CLI exige --output, vérifie taille et empreinte, puis écrit exclusivement dans un fichier neuf. Elle ne remplace jamais un fichier existant.

La recette doit produire une description pour chacun des trois dossiers Asteria, la valider hors ligne contre le [schéma officiel OpenAPI 3.1 du 7 octobre 2022](https://spec.openapis.org/oas/3.1/schema/2022-10-07), comparer les octets CLI/API/MCP et après restauration, et refuser lectures transverses, descripteurs altérés et schémas non supportés. La fixture officielle est épinglée par SHA-256 et accompagnée de sa provenance et de sa licence. Les tests du schéma ne valent pas test d’une API métier déployée.
