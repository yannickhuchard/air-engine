# ADR 0033 - Transport HTTPS direct et explicite

Statut : adopté, tranche 16. SQLite/local/Python seul demeurent le chemin initial.

Le serveur d’équipe termine TLS dans Uvicorn avec les fichiers de certificat et de clé choisis par l’opérateur. Le service accepte une seule origine déclarée et une adresse d’écoute IP. Cette première configuration ne délègue pas l’identité du transport à des en-têtes de proxy. CLI et MCP stdio partagent un transport urllib borné ; toutes les redirections sont refusées, y compris locales. La vérification de chaîne et de nom reste obligatoire et TLS 1.2 est le minimum.

server-configure intervient après arrêt vérifié, conserve les autres champs de configuration et écrit atomiquement. Le contrôle de démarrage/arrêt rejoint directement l’adresse d’écoute avec le nom TLS déclaré, ce qui évite d’exiger un SAN localhost/IP dans un certificat d’entreprise. Son état ne contient aucune clé privée. Un échec de démarrage nettoie uniquement l’arbre de processus qu’il a créé.

La restauration d’une sauvegarde rétablit une écoute locale et une nouvelle identité selon le contrat existant. Les clés TLS restent des secrets de déploiement, pas des éléments du registre portable. Une nouvelle configuration TLS doit être appliquée sur le nouvel hôte. Les mandats et la vérification OIDC ne changent pas.

La recette utilise une CA jetable, trois dossiers fictifs et des échanges TLS réels en boucle locale. Elle ne qualifie ni une PKI d’entreprise, ni une installation sur un autre OS, ni un IDE propriétaire. Voir lot-transport-https.md pour les commandes et limites.
