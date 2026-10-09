# ADR-20 - Profil de fondation et baselines fermées

Statut : IMPLEMENTED_SCOPED. Version produit : 0.2.0.dev1.
Références : A.2/A.3/A.11, B.2, C.1 AIR-V003, D.2/D.5 du white paper.

## Décision d’implémentation

Ajouter air.foundation/0.2 comme profil expérimental de réalisation. Il ne désigne
pas une nouvelle version du langage normatif du paper. Conserver les enveloppes
et digests des anciens Scope/Source ; les données bootstrap restent lisibles.
La couverture est déclarée dans capabilities et chaque rapport.

Les références sont exactes et leur type attendu appartient au registre des champs.
Une baseline sélectionne une seule révision par identité et ferme toutes les
références des six types de données acceptés. Les identités de personnes/services
sont des URI externes ; leur résolution effective appartient à L04. Un parent
de baseline doit exister avant son enfant ; il n’est pas un membre du graphe métier.

L’enveloppe reste DRAFT. Figer un ensemble de brouillons n’équivaut pas à accepter
une assertion, publier un package ou approuver un changement. Conserver les
inconnues dans le snapshot et rendre decision_ready=false tant que la chaîne
de décision et de revue n’est pas construite.

Les liens Evidence → Assertion portent une direction explicite SUPPORTS/REFUTES,
ce qui résout l’ambiguïté structurelle de supports_or_refutes pour ce sous-profil.
Les liens réciproques sont contrôlés ; les cycles sont permis. ESTABLISHED est
refusé sans service de revue authentifiée, y compris si le client fournit une
preuve ou une affirmation textuelle d’approbation.

ChangeSet contient des opérations d’objet entier, un vecteur attendu complet et
aucune approbation. Il produit une cible déterministe et distincte. Cible, ChangeSet
et événements d’audit sont engagés dans la même transaction. Un conflit de contenu
sur le ChangeSet annule également la création de sa cible. Aucune réservation,
fusion avec une tête mutable ou approbation implicite.

Le lockfile est une projection canonique des membres typés et de leurs digests,
adressée par SHA-256. Son contenu est reconstruit lors de l’export ; les empreintes
du manifeste, des membres et du lockfile sont contrôlées. Aucun stockage externe
ni téléchargement n’est requis. Les payloads utilisent le registre existant,
identique sur SQLite et PostgreSQL ; aucune migration SQL dans cette tranche.

## Limites explicites

AIR-V003 est exécuté pour les six types déclarés uniquement. Les autres règles,
la qualification des sources, la détection générale des contradictions, les
permissions fines, les baselines de profils complets et la publication sont hors
réception. Le contrôle de forme d’une réponse à une Unknown ne prouve pas la
justesse de cette réponse. Le service de décision doit encore porter ces garanties.

Les états, enums et records provisoires sont décrits dans
[le contrat de tranche](../lot-connaissance-baselines.md). Une extension future
versionnera les changements de sémantique et préservera la lecture des anciens
snapshots ; elle ne recalculera pas silencieusement leurs digests.
