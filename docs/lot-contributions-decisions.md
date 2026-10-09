# Contributions et décisions de conception - tranche 13

Version 0.13.0.dev1 ; 243 tests réussis sur SQLite et PostgreSQL 18.6, démonstrations collaboration et M1 PASS_SCOPED. Références : white paper A.8 page 48 et A.11 page 52 ; L06/L08/L15.

Contribution et Decision sont implémentés dans un profil explicite compatible avec les baselines historiques. Conserver leurs champs normatifs ; documenter les enums et restrictions du sous-profil. Les alternatives peuvent être des textes ou références exactes, la sélection doit désigner une alternative déclarée. Les conditions de réexamen restent textuelles dans cette tranche.

Une contribution et une décision importées sont DRAFT et déclaratives. Un service de dépôt authentifié lie l’auteur de Contribution ou l’autorité déclarée de Decision au sujet authentifié, avec transaction, audit et idempotence. Un reçu prouve ce dépôt, pas une délégation métier, une revue indépendante ou une autorisation de modifier un système. Les services de revue et d’admission conservent leurs propres exigences.

Le traitement d’une Drift peut pointer une Contribution ou une Decision exacte. La résolution d’une Contribution peut pointer une Decision ou un ChangeSet. Les révisions précédentes restent immuables ; aucune dérive ne sera automatiquement fermée par l’existence d’une décision.

La recette prolongera les trois dossiers Asteria : partir des écarts calculés, déposer une contribution, enregistrer une décision de conception et produire de nouvelles révisions explicites des liens de traitement. Vérifier les auteurs falsifiés, les références hors périmètre, les sélections absentes, l’idempotence, la fermeture des baselines et le replay après restauration. Les systèmes ERP, atelier et IAM restent externes et non exécutés.

## Services et commandes

whoami lit l’URI du sujet authentifié. collaboration-submit reçoit une clé d’idempotence et un objet Contribution ou Decision ; collaboration-read reçoit la référence exacte du reçu. Les outils MCP sont air_whoami, air_collaboration_submit et air_collaboration_read, sur les mêmes services. Le dépôt exige write sur le namespace et read sur toutes les dépendances, puis revalide l’identité dans la transaction.

Le catalogue comprend 22 types persistables ; le profil collaboration ajoute deux types de données aux 18 du profil runtime. Les anciens profils restent inchangés. Voir ADR 0030 pour les identités, enums, alternatives et limites de fermeture des références à ChangeSet.

## Démonstration

scripts/demo_collaboration.py rejoue les observations et fait intervenir deux sujets distincts dans chacun des trois dossiers : contribution opérationnelle, décision d’architecture et résolution documentée. Les traitements proposés sont la mise en attente SAV, une mesure fraîche pour l’atelier et l’examen RH/IAM du conflit d’identité.

Chaque dossier produit une nouvelle baseline de 30 objets. La dérive et l’incident ont une nouvelle révision ; leurs anciennes révisions restent lisibles. Aucun incident n’est automatiquement déclaré réparé. Les auteurs falsifiés et lectures transverses sont refusés ; le replay CLI/HTTP/MCP et la restauration des baselines et reçus sont identiques.
