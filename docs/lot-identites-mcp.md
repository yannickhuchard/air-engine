# P04 - Identités, mandats et transports MCP

Le catalogue et le contrôle préalable d'appel partagent `air.tool_access`. Ils exposent uniquement les
actions accordées au rôle et à au moins un namespace de l'identité authentifiée. Chaque service vérifie
ensuite les namespaces exacts, les dépendances et l'auteur propriétaire quand nécessaire. L'administrateur
n'a aucun passe-droit sur les namespaces ; les mandats métier restent explicites.

| Identité AIR | Capacités usuelles avec une politique explicite |
| --- | --- |
| reader | Lectures autorisées et calculs purs ; aucun dépôt d'architecture ni engagement |
| editor avec write | Lectures et dépôts dans les namespaces accordés |
| relecteur : editor avec review | Lectures et revues mandatées ; write n'est pas implicite |
| admin | Actions accordées par la politique ; publish/admit/activate/capacity ne sont jamais implicites |

Les jobs sont des calculs purs : leur soumission peut être autorisée en lecture et leur annulation reste
réservée à leur propriétaire authentifié. Le catalogue ne remplace pas le contrôle de propriété du service.
Les identités sans action de lecture ne voient que les outils de capacité générale et d'identité.

## Même identité, même capacité

Stdio interroge l'identité courante à chaque découverte et appel ; il ne conserve plus le rôle en cache.
Le fichier de connexion est relu, donc une rotation est prise en compte sans redémarrer le processus.
HTTP authentifie chaque requête et emploie le même calcul de catalogue. Un profil local `--access read`,
`contribute` ou `guided` peut restreindre davantage ; `all` ne peut jamais augmenter l'autorité réelle.
Sans identité valide, stdio expose un catalogue vide et refuse les appels ; HTTP répond 401. Il n'y a pas
de notification de catalogue poussée : un client qui le cache doit refaire `tools/list`.

`whoami` indique `identity_binding: CONNECTION_CREDENTIAL`. Le client, les paramètres, les métadonnées d'un
document et les instructions importées ne choisissent jamais l'acteur authentifié. Chaque personne doit
utiliser son propre fichier de connexion ou son jeton OIDC individuel. Un tunnel ou service partagé utilise
**une seule identité AIR** ; il n'implémente pas un SSO individuel et ses revues ne prouvent pas quel humain
était devant le client. Isoler ce compte de service et limiter sa politique. Les parcours OAuth natifs et
les IdP réels restent à recevoir en P07/P09.

## Droits sur les résultats et écritures

Toute transaction déclenchée par une requête authentifiée revérifie jeton et politique au début et avant
commit ; une perte de politique dans la transaction entraîne son rollback. Une réponse réussie est aussi
revérifiée avant son émission, pour ne pas livrer un calcul dont l'accès a été retiré pendant son exécution.
Les revues et leurs révocations revérifient également leur autorité dans leur service. Les qualifications P03 revérifient
mandats, clés, rapports et contexte à la lecture. Les changements préparés doivent encore appartenir à
l'acteur **et** rester lisibles sous la politique courante : le cache ne conserve pas un ancien droit.
Les exports et baselines demandent la fermeture des droits ; les pièces jointes et captures demandent
leurs droits courants, y compris sur le contexte source. Les jobs recontrôlent identité et politique avant
publication, et leur résultat reste protégé par la propriété et les droits sur les entrées.

Les traces MCP ne contiennent ni arguments ni résultats : identifiants de requête textuels hachés,
méthodes/outils limités au vocabulaire connu, aucun champ libre provenant d'une source. Le jeton actif
est masqué s'il est réfléchi dans un diagnostic ou un payload MCP. Ne pas fournir de secrets comme données
métier : ce mécanisme n'est pas un outil universel de détection de secrets dans des documents arbitraires.

La recette couvre lecteur/éditeur/relecteur/administrateur sur deux équipes, les deux transports, les appels
interdits, le retrait de politique, la révocation/rotation en session, les paramètres d'identité forgés,
les textes demandant une élévation et le refus d'accès au cache ou aux artefacts après retrait du mandat.
Les tests existants d'exports, de jobs et de captures complètent la matrice. Une recette protocolaire ne
qualifie pas encore l'interface native de ChatGPT ou Claude, ni la charge ou l'exploitation générale.
