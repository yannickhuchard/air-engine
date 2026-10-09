# ADR 0031 - Workbench HTML autonome

Statut : adopté pour le binding air.workbench/0.14. L08.1/L08.3/L08.4.

Le Workbench est une projection d’une baseline exacte et autorisée. Il embarque les objets, références et fonctions d’exploration nécessaires dans un seul HTML, sans connexion réseau, dépendance distante ou jeton. Le générateur contrôle la fermeture des droits avant export ; le lecteur hors ligne ne peut pas réévaluer une révocation survenue après cet export. Le fichier conserve donc la classification et les obligations de diffusion de ses données.

Les modèles restent des données : insertion DOM par textContent, échappement des délimiteurs du JSON embarqué, scripts et styles autorisés par leur empreinte CSP, réseau et soumission de formulaire bloqués. Les artefacts et liens externes ne sont pas téléchargés. La sortie est limitée à 4 MiB pour un contexte de 1 MiB.

Le formulaire prépare une requête collaboration-submit. L’objet reste DRAFT et porte l’identité du contexte de génération ; cette identité et ses droits seront contrôlés à nouveau par le serveur lors du dépôt. Le téléchargement ne modifie pas le registre. Répéter un téléchargement sans modification conserve la même clé d’idempotence. Une URL temporaire de téléchargement reste disponible une minute pour éviter son retrait avant la prise en charge par un navigateur chargé.

La navigation fonctionne au clavier et adapte les panneaux à un écran étroit. Une liste reste disponible sans JavaScript. Les URI et empreintes exactes sont conservées ; les liens de navigation montrent le nom des objets et la nature de leurs relations.

Le runtime reste Python seul. JavaScript et CSS sont des ressources incluses dans le paquet Python ; ils s’exécutent uniquement dans le navigateur de l’utilisateur. Node et Playwright servent à une recette navigateur optionnelle et ne font pas partie de l’installation AIR.

Cette tranche ne fournit pas de session web, de synchronisation en direct, d’éditeur graphique, de revue habilitée ou d’autorisation métier depuis le navigateur. Ces capacités nécessiteront leurs propres contrats.
