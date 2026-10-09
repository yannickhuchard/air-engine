# Accès HTTPS facultatif - tranche 16

Implémenté en 0.16.0.dev1 ; 275 tests passent sur SQLite et PostgreSQL 18.6, avec trois parcours TLS réels et restauration. L01/L04/L05/L16/L17. SQLite et authentification locale restent les valeurs par défaut ; PostgreSQL et OIDC restent indépendants du transport. Aucun module supplémentaire n’est requis pour TLS.

Sans configuration, AIR démarre sur http://127.0.0.1:8740. Un serveur d’équipe déclare une adresse d’écoute IP, une origine HTTPS exacte, un certificat PEM et sa clé privée, et éventuellement un fichier PEM de confiance. TLS est terminé directement par Uvicorn. Aucun certificat de recette n’est généré à l’installation. Les reverse proxies, préfixes d’URL, mTLS et la haute disponibilité ne font pas partie de ce binding.

Créer un fichier de configuration du transport, par exemple :

~~~json
{
  "host": "0.0.0.0",
  "origin": "https://air.example.org:8740",
  "tls_cert_file": "tls/server-chain.pem",
  "tls_key_file": "tls/server.key",
  "ca_file": "tls/enterprise-ca.pem"
}
~~~

Les chemins relatifs se résolvent depuis AIR home. Le nom déclaré doit correspondre au certificat et au DNS de l’entreprise. ca_file est facultatif si la chaîne est reconnue par les autorités de confiance du système. La clé reste dans un emplacement privé accessible au compte du service ; le fichier de configuration n’en contient que le chemin.

Avec le Python du venv : arrêter le serveur vérifié par scripts/install.py --stop, puis exécuter python -m air --home <home> server-configure <fichier.json>. La commande valide les fichiers et leur paire certificat/clé, puis remplace atomiquement la configuration en conservant identité, stockage et authentification. Elle refuse de modifier le transport tant que server.json indique un serveur à arrêter. Relancer avec python scripts/install.py --start ; le port vient de l’origine déclarée. Un --port explicite différent est refusé. Fournir un fichier contenant {} à server-configure rétablit le transport local.

Un poste client a seulement besoin du runtime AIR et d’un fichier de jeton protégé. Par exemple : python -m air --home <client-home> whoami --url https://air.example.org:8740 --ca-file <ca.pem>. Les mêmes options sont disponibles sur les commandes HTTP et sur python -m air.mcp. Le client ne doit pas posséder la base du serveur. Le protocole MCP HTTP reste disponible à l’URL /mcp, avec Bearer et les en-têtes définis dans mcp.md.

Le client vérifie la chaîne et le nom du serveur ; il ne propose aucun mode sans vérification. TLS 1.2 est le minimum. Les URL avec identifiants, paramètres, fragments ou préfixe de chemin sont refusées. Les redirections ne sont jamais suivies et les proxies hérités de l’environnement ne sont pas utilisés. HTTP sans TLS est limité aux origines de boucle locale. La réponse des adaptateurs est bornée à 8 MiB.

L’API TLS et MCP vérifient Host et Origin avant traitement, refusent les valeurs multiples et ignorent les en-têtes de proxy. Aucun droit supplémentaire n’est accordé par le transport. Un jeton local reste révocable ; OIDC continue à vérifier signature, issuer, audience et expiration. La qualification d’un vrai fournisseur OIDC reste distincte des tests de jetons signés.

L’installateur contrôle health en se connectant à l’adresse d’écoute locale tout en vérifiant le nom déclaré du certificat. Le certificat n’a donc pas besoin d’un SAN IP de boucle locale. L’arrêt utilise l’adresse sauvegardée au démarrage, vérifie instance et PID, et refuse d’arrêter un processus non identifié. Un démarrage qui ne devient pas sain nettoie seulement son propre arbre de processus. Une restauration de registre revient au transport local : elle ne distribue ni n’active automatiquement les clés TLS de l’ancien hôte.

La recette facultative scripts/qualify_https.py prolonge scripts/demo_business.py : elle restaure une copie isolée des trois dossiers, utilise une CA jetable et un certificat DNS localhost, puis vérifie CLI/API/MCP HTTPS, nouvelles contributions idempotentes, séparation des droits et restauration. scripts/tls_fixture.py nécessite cryptography pour cette recette seulement ; l’extra oidc l’apporte. Aucun port public, PKI d’entreprise ou système ERP/atelier/IAM n’est modifié.

Références : [contrôle TLS de Python](https://docs.python.org/3/library/ssl.html), implémentation Uvicorn installée et contraintes du projet. Les tests de transport sont dans tests/test_transport.py.
