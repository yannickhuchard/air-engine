# ADR 0026 - Jobs purs et reprise par bail

Statut : accepté pour air.jobs/0.9, schéma SQL 3.

La demande, les claims, l’annulation et le résultat terminal sont des reçus immuables. Une projection job_state indexée par statut et échéance permet au worker de trouver les travaux prêts. Le claim est transactionnel et porte une génération. PostgreSQL utilise FOR UPDATE SKIP LOCKED ; SQLite utilise son verrou d’écriture. Le calcul s’exécute après commit du claim, sans garder une transaction ouverte.

La fin vérifie génération, claim courant, bail, identité et politique avant de publier le résultat. Une annulation terminale ou un worker plus récent empêche un ancien worker de publier. Trois tentatives constituent la limite du binding initial. Les erreurs de stockage laissent le bail récupérable plutôt que d’inventer une réussite.

Le worker intégré maintient l’installation Python seule. --no-worker et worker-once offrent une séparation explicite sans modifier le noyau. Il ne s’agit pas d’un sandbox pour du code arbitraire : seules trois fonctions pures et bornées sont autorisées. Le job n’a aucune commande système, requête réseau métier ni callback fourni par le client.

La délégation conserve identifiant de jeton local ou expiration/configuration OIDC, et identifiant d’installation ; aucun jeton en clair. La consultation du résultat vérifie les droits actuels. La reprise d’une autre installation ne renouvelle pas implicitement une autorisation différée.

La projection est vérifiée à l’import du registre. Les exports du schéma 2 restent importables avec création de la projection vide ; les sauvegardes SQLite 1 et 2 migrent vers 3. Le schéma n’ajoute aucun type AIR normatif : les jobs sont des contrats de service du sous-ensemble livré.
