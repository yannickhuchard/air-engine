# Tranche 05 - projections, accès, revues et MCP

Cette tranche conserve les 17 types et le profil construction/0.4. Elle ajoute des services versionnés ; un reçu de revue n'est pas un nouvel objet normatif du white paper.

## Comparer et présenter

Les commandes diff, impact et view utilisent l'API authentifiée. Leurs demandes fixent chaque baseline par id, revision et digest SHA-256. Un digest différent est refusé. diff expose les ajouts, retraits et champs modifiés avec chemins JSON Pointer ; les tableaux sont comparés comme valeurs normalisées. Cela ne prouve pas la compatibilité sémantique des comportements.

impact suit les références inverses exactes, avec chemins et qualification POTENTIAL_REFERENCE_DEPENDENCY. Il examine seulement les baselines fournies, au maximum 32, et 256 cibles. Les cycles sont supportés ; budgets de 10 000 pas de chemins et 8 MiB de résultat. Une limite dépassée est une erreur, jamais une réponse tronquée présentée comme complète.

view produit un HTML autonome sans JavaScript, avec échappement et politique CSP restrictive, les chaînes exigence/fonction/contrat/unité, scénarios prévus, inconnues, sources et mappings. Aucun déplacement visuel ne modifie le modèle. Les VerificationCase restent NOT_EXECUTED. La lecture d'une baseline exige l'accès à sa fermeture de références, y compris ses dépendances partagées.

~~~sh
python -m air diff diff-request.json
python -m air impact impact-request.json
python -m air view view-request.json --output dossier.html
~~~

view-request.json contient un objet baseline avec id, revision et digest. diff-request.json contient before et after de cette forme. impact-request.json contient baselines (liste de cette forme) et targets (id/revision). Les endpoints sont POST /v1/diffs, /v1/impacts et /v1/views. Le fichier de sortie view doit être nouveau.

## Accès par périmètre

Sans fichier de politique, reader lit le référentiel commun et editor/admin écrivent ; aucun rôle ne possède implicitement review, publish, admit ou activate. Pour compartimenter, l'opérateur OS applique une politique explicite :

~~~json
{"version":"company-1","subjects":{"architect-sav":{"read":["asteria.sav","asteria.shared"],"write":["asteria.sav"]},"reviewer":{"read":["asteria.sav","asteria.shared"],"review":["asteria.sav"]}}}
~~~

~~~sh
python -m air policy-set company-policy.json
~~~

Le fichier privé access-policy.json remplace atomiquement la politique et est relu à chaque requête. Une action ou un sujet absent n'a aucun droit. Le joker * accorde tous les namespaces pour l'action indiquée. Un reader ne peut écrire ou revoir même si la politique lui accorde ces actions. Un administrateur n'outrepasse pas une politique explicite. Les ACL par champ/aspect, groupes et délégations restent à compléter. La politique est limitée à 64 KiB ; un fichier invalide bloque les routes protégées.

## Reçus de revue

POST /v1/reviews et la commande review reçoivent idempotency_key, baseline, target, outcome (ACCEPTED/REJECTED), rationale, evidence (Sources/Evidence exactes avec digest), expires_at UTC. Les cibles prises en charge sont Assertion, Requirement, SemanticContract et Baseline. L'acteur provient de l'authentification ; la politique doit explicitement accorder review au namespace cible. L'auteur authentifié ne peut revoir son propre contenu ; pour une baseline, cela inclut les auteurs des membres.

Le reçu immuable lie la demande, le digest de politique, le rôle et l'acteur. Une répétition identique retrouve ce reçu, une réutilisation différente de clé est refusée, y compris sous concurrence. L'expiration initiale doit être future et à moins de 366 jours. GET /v1/reviews/{id} évalue l'effectivité ; révocation, expiration ou changement de politique la retirent. POST /v1/review-revocations reçoit review_id et rationale, avec le même mandat requis. Ces décisions sont auditées.

Le reçu atteste une décision d'un principal authentifié, pas que l'acteur est nécessairement un humain, ni la vérité scientifique de la preuve, ni l'exécution d'un test. Il ne promeut pas une Assertion en ESTABLISHED, ne fait pas passer les portes de construction et n'autorise publication, admission ou activation. Les jetons d'agents devraient conserver read/write sans review ; la séparation des identités relève de la politique de l'entreprise.

## MCP et stockage

Voir [le binding MCP](mcp.md). Les services de projection et de revue partagent les contrôles de l'API. Le schéma SQL passe de 1 à 2 par ajout de service_record et de son index ; les objets, digests et jetons existants ne sont pas réécrits. Arrêter le service et sauvegarder avant une mise à jour. L'installateur applique la migration, le serveur refuse un schéma ancien.

Les commandes backup et restore décrites dans installation.md visent SQLite. Elles conservent les reçus historiques ; la restauration change l'identité d'instance, révoque les anciens jetons et modifie la version de politique pour exiger une revalidation des revues. Elles ne qualifient pas encore la restauration d'engagements, non implémentés dans cette tranche.
