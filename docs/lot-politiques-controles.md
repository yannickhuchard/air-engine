# Politiques, contraintes et contrôles - tranche 25

Contrat du binding expérimental air.governance/0.25, à partir de la page 48 du white paper. Le sous-périmètre 0.25 est qualifié par 410 tests sur SQLite et PostgreSQL 18.6, puis par six diagnostics dans les trois dossiers. Six types DRAFT sont concernés : Constraint, Control, Obligation, Policy, Risk et Waiver. Aucun changement du schéma SQL 6 n’est requis.

## Déclarations et références

Les champs reprennent les éléments décrits dans le white paper. Constraint lie périmètre, sources, condition, mode hard/soft et VerificationCase. Control décrit mécanisme, responsable, vérifications et exigences de preuve. Obligation relie Source, interprétation, Decision d’applicabilité et contrôles. Policy relie émetteur, applicabilité et contraintes. Risk conserve causes, conséquences, méthode déclarée et traitements. Waiver fixe règle concernée, périmètre, échéance, Decision d’approbation déclarée et contrôles compensatoires.

Les collections de références sont des ensembles canonicalisés par identité et révision ; evidence_requirements et consequences sont des ensembles de textes triés. Chaque collection est bornée à 128 éléments. Les références sont exactes et fermées dans la baseline, y compris les littéraux des expressions. Les conditions et applicabilités acceptent un texte ou une expression booléenne AIR-Expr. Un texte n’est jamais converti implicitement en code. Les anciennes baselines restent fermées sur leurs types précédents.

## Diagnostic

policy-check / POST /v1/policies/check / air_check_policy prennent une baseline, une Policy et des contextes typés explicites. Chaque jeu d’entrées de contrainte désigne son objet exact et son empreinte. Les duplications, mauvais types, noms inconnus et références étrangères à la politique sont refusés.

L’applicabilité est évaluée d’abord. Une applicabilité fausse produit NOT_APPLICABLE et ne calcule pas les contraintes. Une applicabilité inconnue, contradictoire ou textuelle ne donne aucun résultat favorable. Les conditions textuelles restent NOT_EXECUTED/UNKNOWN. Les calculs AIR-Expr partagent 50000 étapes pour au plus 128 contraintes ; requête, contexte et rapport sont bornés à 1 MiB.

Le résultat conserve les diagnostics de toutes les contraintes. Une contrainte hard non satisfaite bloque le diagnostic ; une contrainte soft reste signalée, même si elle ne compte pas comme blocage hard. all_constraints_satisfied reste faux tant que l’une des conditions n’est pas satisfaite.

as_of concerne les validités déclarées, sur intervalles demi-ouverts, et les échéances des Waiver. Ce n’est pas une reconstruction de ce que le registre savait à cette date. Les dérogations DRAFT sont montrées comme NOT_VERIFIED et applied=false, même si leur Decision mentionne une approbation. Elles n’effacent aucun résultat défavorable.

Les déclarations ne créent ni mandat, ni politique serveur, ni contrôle externe exécuté. Le service ne donne pas d’autorisation d’admission, d’activation ou de conformité réglementaire. La réception des règles AIR-V036 à AIR-V038 reste ouverte.

## Recette exécutée

Trois dossiers fictifs dans la même entreprise : confirmation ERP, fraîcheur industrielle et cohérence IAM. Les cas nominaux et inconnus/violés/contradictoires sont comparés par CLI/API/MCP, puis restaurés. Une dérogation déclarée laisse le refus visible. Voir docs/traceability/verification-policies.json. Les neuf VerificationCase métier originaux restent NOT_EXECUTED.

La recette utilise as_of=2026-10-06T12:00:00Z, à l’intérieur de la fenêtre fictive Asteria du 5 octobre au 30 novembre. Les échéances de revue et dérogation sont fixées au 20 octobre. Cette date fournie n’est pas l’horloge réelle du serveur.
