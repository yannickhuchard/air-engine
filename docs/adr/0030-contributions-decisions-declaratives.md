# ADR 0030 - Contributions et décisions déclaratives

Statut : adopté pour le sous-profil expérimental air.collaboration/0.13. Références : A.8 page 48 et A.11 page 52 du white paper.

Contribution et Decision conservent leurs champs normatifs. Les kinds de contribution sont QUESTION, PROPOSAL, CRITIQUE, REVIEW et RESOLUTION. Une contribution REVIEW ne constitue pas un reçu de revue habilitée. Les alternatives de décision sont des textes ou des références exactes ; la sélection doit correspondre à l’une d’elles. Les conditions de réexamen sont textuelles, sans évaluation automatique dans ce sous-profil.

L’identité des objets est une URI. Les sujets locaux et OIDC pouvant être de simples chaînes, whoami retourne une URI déterministe dérivée de l’identifiant d’instance, du mode d’authentification, de l’émetteur OIDC éventuel et du sujet. Le renouvellement d’un jeton ne change pas cette URI. Une restauration créant une nouvelle instance produit une nouvelle identité ; les reçus historiques conservent leur identité d’origine. Les identités de deux émetteurs ou instances ne sont pas fusionnées implicitement.

Le service de dépôt vérifie que author ou authority et provenance.recorded_by correspondent à cette identité. Il contrôle les droits, les références et l’identité courante, puis enregistre objet, reçu et audit dans une même transaction. Le reçu prouve le dépôt authentifié du DRAFT. Il ne qualifie ni la vérité du contenu ni la délégation métier ni une présence humaine. Un import générique reste déclaratif et ne fabrique aucun reçu de dépôt authentifié.

Les références target, basis et alternatives pointent les types de données du profil. Une résolution vers Decision est fermable dans une baseline collaboration. Une résolution vers ChangeSet est persistable et vérifiée au dépôt mais ne peut pas encore être membre d’une baseline fermée, le modèle de fermeture des ChangeSet n’étant pas étendu dans cette tranche. Les références à une baseline comme cible restent hors sous-profil. Cette restriction est explicite, sans affaiblir AIR-V003.

Les alternatives, références target et basis sont normalisées comme ensembles. L’ordre des conséquences et conditions de réexamen est conservé. Une baseline sélectionne toujours une seule révision par identité. Le démonstrateur relie les nouvelles décisions à l’observation et à l’attente exactes ; il ne mélange pas deux révisions d’une dérive dans une même baseline.

Aucune politique SQL, réservation ou autorisation d’activation ne peut être modifiée par le simple dépôt de ces objets. Les transitions des services d’autorité restent distinctes.
