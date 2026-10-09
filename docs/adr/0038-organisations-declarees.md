# ADR 0038 - Organisations et autorités déclarées

Statut : accepté pour air.organization/0.21.

Le white paper distingue domaines, unités organisationnelles, rôles et autorités. Le registre d’admission et les politiques de namespace existants accordent des droits effectifs ; les brouillons importés ne peuvent se substituer à ces mécanismes.

Quatre types DRAFT enrichissent les données : Role, OrganizationUnit, AuthorityScope et Domain. Actor.roles reçoit des références exactes vers Role. Le nouveau profil de baseline comporte 35 types de données ; les sept précédents restent figés. View demeure un produit géré extérieur à ces profils.

Les relations parentales d’OrganizationUnit sont acycliques. Dans ce binding, Domain et AuthorityScope doivent partager le même Scope exact. Les responsabilités, décisions permises, limites et compétences restent déclaratives. SkillRequirement reçoit un binding explicite air.skill-requirement/0.21 avec competency, minimum_level et assessment_method textuels. Les délégations doivent être vides ; OperatingModel et l’évaluation des limites par expression ne sont pas revendiqués.

La lecture organisationnelle utilise une baseline exacte et le contrôle complet des droits avant de produire un rapport déterministe. Elle ne crée aucune autorisation, qualification de compétence, délégation ou réservation. SQLite/local reste le mode initial ; le schéma SQL 6 reste inchangé.
