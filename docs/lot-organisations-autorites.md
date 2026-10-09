# Organisations, rôles et autorités déclarées - tranche 21

Binding expérimental qualifié sur SQLite et PostgreSQL 18.6 : les pages 45 et 51 du white paper définissent Domain, OrganizationUnit, Role et AuthorityScope. Cette tranche relie les acteurs de dossiers à une organisation versionnée, sans transformer les déclarations en droits effectifs.

Le profil air.organization/0.21 ajoute ces quatre types aux 31 types de données du profil audience/0.19. Les anciens profils conservent leurs listes de membres et empreintes. Actor.roles référence des Role exacts ; un Actor dont cette liste est non vide requiert le nouveau profil dans une baseline. Les audiences Viewpoint restent des Stakeholder dans ce binding.

Domain a purpose, scope et authority obligatoires. Son périmètre doit être exactement celui de son AuthorityScope ; un Domain n’est pas automatiquement une équipe. OrganizationUnit a un mandat, un parent facultatif et des rôles ; les cycles parentaux sont refusés. OperatingModel n’étant pas encore implémenté, ce champ facultatif n’est pas accepté silencieusement.

Role a des responsabilités non vides, des compétences requises et une autorité facultative. Le record SkillRequirement reçoit un binding expérimental explicite : compétence et niveau minimum textuels, méthode d’évaluation textuelle. Il ne prétend pas vérifier une qualification humaine ou agentique. AuthorityScope conserve principal URI, Scope exact, décisions permises, limites textuelles non vides et règles de séparation. Les expressions et délégations exécutables restent hors périmètre ; la liste delegations doit être vide dans ce premier contrat.

Un service de lecture prend une baseline exacte et retourne équipes, rôles, acteurs, domaines et autorités déclarées, avec leurs références et limites. Il contrôle toute la fermeture des droits avant lecture. Il ne modifie aucune politique de namespace, ne crée aucun mandat d’admission et ne calcule pas une autorisation depuis le texte. L’interface, la CLI et MCP appellent ce service commun.

La recette ajoute une direction d’architecture partagée et trois équipes crédibles aux dossiers SAV, atelier et IAM, avec responsabilités et limites distinctes. Elle vérifie références, cycles, ancien profil, droits croisés, replay et restauration. Les observations métier et portes existantes restent visibles sans nouvelle qualification implicite.

## Commandes

organization-inspect prend un fichier JSON contenant baseline avec id, revision et digest exacts. Exemple : python -m air organization-inspect organization-request.json. POST /v1/organization/inspect et MCP air_inspect_organization appellent le même service de lecture. La réponse contient units, roles, actors, domains, authorities, request_digest et report_digest ; chaque entrée conserve sa référence exacte, son namespace, sa validité déclarée et son corps de modèle. Les données ne sont pas filtrées par date ou promues en autorité effective. Le contexte et le rapport sont bornés à 1 MiB.

Exécuter scripts/demo_organization.py après scripts/demo_audience.py. La démonstration crée une installation isolée, trois baselines de 58 objets et une direction d’architecture partagée. Les équipes gardent leurs droits de dossier et la lecture du namespace commun. Les nouvelles déclarations n’altèrent pas les acteurs déjà figés dans les contrats historiques. Les rapports sont comparés par CLI/API/MCP puis après restauration.

## Réception de cette tranche

333 tests passent sur chaque moteur. Les dix cas organisationnels couvrent graphes, cycles, mauvais types, canonicalisation, refus de lecture, transfert et équivalence API/MCP HTTP. Les trois parcours CLI/API/MCP et leurs restaurations passent ; DEMO-METIER-1 a été rejoué. La conformité normative complète reste ouverte.
