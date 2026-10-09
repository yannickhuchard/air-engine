# ADR 44 - Compilation déterministe d’une description OpenAPI

Décision du 20 septembre 2026 : ajouter air.openapi-compiler/0.27 comme contrat de service pur, sans type normatif supplémentaire ni migration SQL. La description cible OpenAPI 3.1.1 et les bindings HTTP/JSON explicites de 0.26.

Chaque schéma provient d’un manifeste local autorisé et vérifié. Les références distantes sont refusées. Les nombres décimaux restent exacts ; la sortie JSON triée possède sa propre empreinte d’octets, sans revendiquer JCS. Les mappings relient le produit aux objets exacts, artefacts et paramètres de requête. Le générateur observé est conservé dans le rapport.

La compilation expose ses pertes : sécurité non traduite, comportement non implémenté, erreurs non mappées, correspondances d’entités non qualifiées et éventuelles opérations absentes. Le résultat DRAFT_DESIGN_ONLY n’est ni déployé ni admis. Les références de contrôles ne deviennent pas des mécanismes d’authentification inventés.

La CLI vérifie l’empreinte et écrit un fichier neuf. Les recettes comparent CLI/API/MCP et restauration ; le schéma officiel OpenAPI est épinglé comme fixture de test avec provenance et licence. Aucun téléchargement de schéma n’est effectué au runtime.
