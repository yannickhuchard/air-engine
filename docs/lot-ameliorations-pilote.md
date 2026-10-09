# Améliorations issues du pilote assurance santé - tranche 30

Cette tranche ne vient pas d’un plan : elle vient d’un pilote réel. Deux projets d’architecture de solution ont
été conduits de bout en bout avec AIR 0.29 - une plateforme d’assurance santé (cinq contextes bornés, 28 opérations,
un serveur MCP et quatre bancs) et un système de gestion de la fraude partagé, temps réel, sur le cycle détecter,
évaluer, agir, escalader. L’usage a produit **27 constats datés et prouvés** ; 22 sont corrigés ici, dont les
quatre bloquants. Le dossier du pilote, son journal de constats et les deux passes sont décrits dans
[retour du pilote assurance santé](retour-pilote-sante.md).

## Ce qui empêchait de décrire une API standard

| Constat | Correction |
| --- | --- |
| Les chemins REST à paramètre étaient refusés (18 des 28 opérations) | Binding `air.http-json-mapping/0.30` : gabarits `{param}`, chaque gabarit doit correspondre à un paramètre déclaré `in: path`, et réciproquement |
| Le contrat d’erreur déclaré n’apparaissait nulle part | Chaque opération associe un code du contrat à un statut 4xx/5xx et à un schéma ; l’OpenAPI porte les réponses en `application/problem+json` |
| Ni paramètre de requête ni en-tête | Paramètres typés `path`, `query`, `header` avec format, énumération et description |
| Aucun schéma de sécurité | `security_scheme` déclaratif (bearer, clé d’API, mTLS, OAuth2 client credentials) généré et marqué non vérifié |
| Composants nommés par empreinte | Composants nommés d’après le DataSchema (`ClaimSubmission`, `Claim`…) ; l’empreinte reste dans le rapport |
| Opérations muettes | `description` reprise de la Function et un tag par contrat |

Le binding 0.26 reste valide et inchangé : un objet existant se valide exactement comme avant, et un chemin à
gabarit y reste refusé. Les deux versions coexistent dans une même baseline.

## Ce qui empêchait de décrire un agrégat

`air.structured-json/0.30` remplace le sous-ensemble plat **pour la compilation** : objets imbriqués, tableaux
d’objets ou de scalaires, `pattern`, bornes, profondeur maximale 6, 512 nœuds, aucune référence ni composition.
Tout schéma plat reste valide. `data-validate` conserve `air.flat-json/0.23`.

Le sous-ensemble est désormais vérifié **à l’inspection**, avant toute compilation : chaque binding rapporte
`schema_artifacts_validated` et l’écart devient une violation nommée. Un refus de compilation liste tous les
schémas fautifs avec leurs identifiants et tous leurs écarts, au lieu du premier rencontré.

## Ce qui n’était pas vérifiable : DDD et MECE

L’inspection d’architecture (`air.architecture-checks/0.30`) exécute dix contrôles **structurels** sur les objets
que la baseline possède :

- exclusivité - une fonction exposée par un seul contrat, des noms d’opération uniques, un bloc propriétaire par
  agrégat, un fournisseur par contrat ;
- exhaustivité - chaque exigence fonctionnelle MUST satisfaite, chaque fonction réalisée par un bloc, chaque
  contrat requis fourni ;
- cohérence de contexte - un bloc ne possède que des agrégats d’une même autorité de données, un événement est
  délivré par le contrat du bloc qui possède l’agrégat représenté ;
- schémas déclarés dans le sous-ensemble de compilation.

Ce que l’inspection **ne** vérifie pas reste écrit dans le rapport (`not_checked`) : appartenance d’un bloc à un
contexte borné (convention de nommage), écriture d’un agrégat par une commande, types de relation de carte de
contextes, et toute vérité de comportement. Une violation est structurelle ; elle ne juge ni la conception ni la
sémantique.

## Ce qui empêchait de décrire un cycle temps réel

`air.message-channel-mapping/0.30` déclare un canal de messages sur un `TechnicalBinding` : protocole (KAFKA,
AMQP, MQTT, NATS), canal, action `PUBLISH` ou `SUBSCRIBE`, événement exact, schéma de message, clé de partition,
ordre et garantie de livraison. Un binding déclare des opérations HTTP **ou** des canaux, jamais les deux. Le
message d’un canal doit être le schéma de charge utile exact de son événement, et l’événement doit être délivré
sous le contrat du binding. L’inspection rapporte la couverture : un événement porté par le contrat sans canal
est signalé.

Rien n’est exécuté : aucun courtier n’est contacté, l’ordre et la livraison sont déclarés, pas vérifiés. La
génération d’une description AsyncAPI reste à faire.

## Ce qui rendait une dépendance entre projets coûteuse

Une baseline est fermée : référencer un objet d’un autre projet impose d’en recopier la fermeture. Le pilote a
mesuré 5 références → 69 objets, découverts par essais successifs. `air.baseline-closure/0.30`
(`air baseline-closure`, outil MCP `air_compute_baseline_closure`) calcule cette fermeture depuis des baselines
épinglées, lues avec la politique de l’appelant : membres, répartition par namespace et par type, références non
résolues et racines introuvables. Il n’écrit rien et ne crée aucune baseline. Dans le pilote, il a immédiatement
révélé que la fraude épinglait encore des révisions périmées de la plateforme.

L’index de portefeuille classe maintenant un objet d’un autre dépôt **déclaré** comme dépendance référencée ;
seul un namespace non déclaré bloque. Les totaux distinguent objets possédés et objets référencés.

## Diagnostics et poste de travail

- Chaque diagnostic de validation nomme l’objet concerné (identifiant, révision, type), pas seulement sa position.
- `AIR_REFERENCE_MISSING` nomme la cible manquante.
- Un refus d’accès renvoie la liste des références indisponibles que l’appelant a lui-même fournies ; rien d’autre
  n’est divulgué.
- La CLI prend le port de l’instance désignée par `--home` (ou `AIR_HOME`) ; `--port` et `--url` restent prioritaires.
- Une connexion impossible répond `AIR_UNREACHABLE` avec l’origine tentée, la cause et une indication.
- La sortie standard est en LF sur tout système.
- Chaque dépôt produit contient un `.gitattributes` et le plan tolère un fichier texte extrait en CRLF : un clone
  d’équipe sous Windows ne produit plus de conflit.

La porte de construction accepte enfin un profil qui contient les types de construction : le dossier d’architecture
complet passe la porte sans seconde baseline.

## Ce qui reste ouvert

| Constat | Raison |
| --- | --- |
| Composition de blocs et binding MCP (outils par banc) | Nouveau type de relation et binding client ; le serveur MCP unique reste décrit par des responsabilités et des fonctions |
| Relations du langage omniprésent et carte de contextes | `Concept.semantic_relations` est borné à zéro ; les relations client/fournisseur, ACL ou noyau partagé n’ont pas de type |
| Conditions de flux de workflow en AIR-Expr, terminaux conditionnels, délais par pas | Le cycle de la fraude reste décrit avec des conditions en texte |
| Rejeu : stimulus attendu refusé, état de départ explicite | Deux scénarios restent nécessaires pour tester une propriété négative |
| Motifs d’identifiant local incohérents entre types | Demande une version de binding pour les machines à états et les workflows |
| Génération AsyncAPI depuis un binding de messagerie | Le canal est déclaré et contrôlé ; la description reste à produire |

## Vérifications

Les recettes du pilote sont rejouées dans `scripts/demo_pilote.py` (tranche 29) ; la passe 2 du pilote assurance
santé est décrite et chiffrée dans [retour du pilote](retour-pilote-sante.md) avec, pour chaque constat, la mesure
avant et après. Aucune conformité AIR complète n’est revendiquée ; les contrôles ajoutés sont structurels et
n’autorisent rien.
