# Production initiale sur le poste de l'architecte

Décision utilisateur du 26 septembre 2026 : la première production d'AIR concerne des
installations autonomes sur les machines des architectes. Le serveur centralisé sera envisagé
plus tard, lorsque l'adoption multi-entreprise le justifiera. Aucun seuil chiffré n'est encore fixé.
Cette décision précise le périmètre de réception ; elle ne transforme pas les essais non exécutés
en succès. La candidate rc8 implémente le [diagnostic et la réception technique du profil local](lot-poste-local.md).

## Finalité et topologie

AIR accompagne le design logique vers un modèle vérifiable et simulable, puis produit les plans
et dossiers pour les ingénieurs, chefs de projet et équipes ops. Exécuter une simulation du modèle
ne revient pas à développer, déployer ou exploiter la solution décrite. Sa future infrastructure
de production n'est pas un prérequis pour remettre les livrables d'architecture.

Chaque architecte utilise un home privé, une base SQLite locale, une identité locale et des clients
effectivement qualifiés. L'API reste sur l'interface de boucle locale ; MCP stdio et les adaptateurs
locaux suivent leurs contrats. Python seul reste suffisant. PostgreSQL, OIDC, Docker, cloud et
serveur partagé ne sont pas requis. Les profils OS de limites globales sont optionnels ; les quotas
applicatifs et limites des calculs restent pertinents pour préserver le poste.

« Décentralisé » signifie ici plusieurs installations autonomes. Cela ne promet ni synchronisation
automatique des registres, ni fusion concurrente, ni fédération distribuée reçue. La collaboration
doit passer par des documents versionnés ou des exports/imports contrôlés, avec provenance, révisions
et revues explicites. Le parcours d'échange entre deux postes et ses conflits doit être qualifié dans
P07/P08. Les bases actives, homes `.air` et identifiants privés ne sont pas des documents à partager.

## Réception G1 recentrée

| Sujet | Nécessaire pour la production sur poste | Reporté au serveur centralisé |
| --- | --- | --- |
| Installation | Installation automatisée, mise à niveau, arrêt maîtrisé, retour arrière ; OS/Python supportés explicitement | Installation d'un service central et topologies partagées |
| Capacité | Dossiers, révisions, pièces jointes et calculs représentatifs d'un poste ; budgets et temps de réponse annoncés et mesurés | Dimensionnement agrégé multi-entreprise, haute concurrence et disponibilité |
| Protection | Home et jetons privés, accès local, autorisations applicables, absence de secrets dans les sorties et exports | SSO/OIDC, PKI serveur, proxy et exposition réseau partagée |
| Conservation | Sauvegarde/restauration du travail, reprise après incident, procédure face à la perte du poste ; rétention expliquée | Service central de sauvegarde hors site, garde institutionnelle des clés et engagements de service |
| Incidents | Diagnostics locaux exploitables par l'architecte/son IDE, espace disque, arrêt brutal et intégrité vérifiés | Collecteur d'alertes d'entreprise et exploitation centralisée |
| Clients | Versions et parcours locaux réellement testés, reprise sans conversation, droits, imports/exports et revues | Clients distants nécessitant une passerelle ou exposition centralisée |
| Réception | Relecture sécurité du périmètre local, pilote indépendant sur postes, support et limites publiés | Réception infrastructure, PKI et exploitation du serveur multi-entreprise |

Le poste conserve un besoin de sauvegarde : une copie sur le même disque ne protège pas sa perte.
La procédure locale doit préciser comment retrouver le travail sur un nouveau poste et quelles données
peuvent être perdues. Cela n'impose pas un service central de sauvegarde à installer avec AIR.

P06 porte désormais sur la fiabilité et la sécurité de cette utilisation locale. P07 doit qualifier
les clients avec cette topologie, sans supposer qu'un client cloud peut joindre `localhost`.
P08 doit recevoir le pilote et les échanges entre postes. Les trois dossiers Asteria restent exigés.
Les statuts de réception restent inchangés jusqu'à vérification des critères applicables.

## Conséquences sur les outils et la suite

Le vérificateur `operations-reception-check` distingue désormais `air.p06-workstation/1` du dossier
serveur historique `air.p06-reception/1`. Le modèle local `p06-workstation.template.json` ne requiert
pas de PKI ou de notification centrale. La recette `qualify_workstation.py` produit ses pièces depuis
des essais isolés, et le vérificateur recalcule les seuils sans auto-valider les preuves absentes.

Après réception technique locale P06, qualifier P07 sur les clients retenus, recevoir P08 sur plusieurs
postes avec les avis indépendants, puis décider G1. La CI reste manuelle et reportée à la
réception de la version de production complète selon la décision utilisateur précédente.

P09/G2 et les recettes d'exploitation centralisée sont différés. Leur reprise demandera un périmètre
explicite : hébergement, isolation entre entreprises, identités, stockage, capacité, support et échanges.
Une centralisation et une fédération entre instances restent deux sujets distincts ; P12 s'appliquera
si une fédération est effectivement retenue. Les obligations normatives G3 restent dans la roadmap.
