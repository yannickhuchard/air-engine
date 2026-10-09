# Distribution libre d’AIR et accès depuis ChatGPT

**Mise à jour du 29 septembre :** moteur rc9 et plugin 0.1.4 publiés, avec exemples
et validation locale. Voir [le reçu courant et les lots restants](distribution-publique-livree.md).
L’évaluation du 28 septembre ci-dessous reste historique.

Évaluation du 28 septembre 2026. Responsable produit et développeur officiel :
**Yannick Huchard**. Ce document décrit une cible et les travaux nécessaires ;
il ne déclare ni publication du moteur ni approbation OpenAI.

## Décision proposée

Distribuer publiquement le moteur et le plugin sous Apache-2.0, avec une installation
autonome par architecte ou entreprise. Python, SQLite et identité locale restent le
socle. PostgreSQL et OIDC restent indépendants et optionnels pour ce socle.
Le référentiel de dossiers appartient à l’utilisateur et reste distinct des dépôts
de logiciel. Aucun compte AIR central ni serveur multi-entreprise n’est requis.

Le plugin public existe : [air-plugin](https://github.com/yannickhuchard/air-plugin),
version 0.1.3. Le moteur reste privé. Pour permettre une installation sans invitation,
il faut une distribution publique accessible du moteur, de ses sources et de sa documentation.
Recommandation : commencer par un dépôt public de sources sélectionnées, sans historique
privé, puis y développer ouvertement. Le nom du nouveau dépôt et sa création ne sont
pas actés par cette évaluation. Rendre public le dépôt privé entier n’est pas nécessaire.

La gratuité de la licence AIR ne rend pas gratuits un abonnement ChatGPT, un domaine,
un éventuel relais réseau ou un support contractuel. L’accès à ChatGPT dépend aussi
de l’offre, de la région et des politiques du workspace ; « pour tous les architectes »
signifie une distribution libre, pas une garantie d’accès à chaque surface ChatGPT.

## Constat vérifié dans le projet

| Élément | État actuel | Conséquence |
| --- | --- | --- |
| Licence | Apache-2.0 confirmée, LICENSE et NOTICE présents | Redistribution permise selon ses conditions |
| Plugin | Public, 0.1.3 ; paquet vérifié | Téléchargeable, mais moteur séparé requis |
| Moteur | Dépôt privé ; wheel et archive reproductibles | Installation publique sans accès privé impossible aujourd’hui |
| Réception locale | G1 sur 0.34.0rc9, Windows 11/Python 3.12.14/SQLite | Ne pas qualifier automatiquement 0.35.0.dev1 ou tous les OS |
| Installation | Python 3.11+, bootstrap, doctor, roue, wheelhouse | Base existante pour un parcours automatisé |
| MCP | stdio et Streamable HTTP, autorisations serveur | Même noyau de conception accessible aux adaptateurs |
| Identité | Jetons locaux ; validation de jetons OIDC externe | Ce validateur n’est pas un serveur d’autorisation OAuth pour ChatGPT |
| ChatGPT | Recettes locales par tunnel consignées en P07/P08 | Preuve ciblée ; aucune preuve de déploiement grand public |
| Annuaire | NOT_SUBMITTED, portail toujours à l’écran de connexion | GitHub public ne vaut ni soumission ni approbation |

Sources locales : `pyproject.toml`, `src/air/auth.py`, `src/air/mcp_http.py`,
`scripts/build_release.py`, [distribution](distribution.md),
[G1](g1-reception-locale.md), [intégrations](integrations-ide.md),
reçu plugin (document historique ou livrable local non inclus).

## Trois parcours à distinguer

| Parcours | Accès au poste | Proposition |
| --- | --- | --- |
| IDE agentique local, notamment Codex | CLI ou MCP stdio, sous les droits accordés | Premier parcours de distribution autonome à recevoir |
| ChatGPT avec connexion MCP configurée par installation | Tunnel autorisé ou endpoint HTTPS accessible au service | Parcours assisté à qualifier sur compte et poste neufs ; disponibilité non universelle |
| Plugin dans l’annuaire public ChatGPT | Serveur MCP déclaré et revu, ou support local explicitement accepté | Cible produit conditionnée par les règles OpenAI |

ChatGPT ordinaire ne reçoit pas l’accès à un serveur `localhost` par le seul ajout
d’un SKILL.md. Une surface ChatGPT Work dotée d’un exécuteur local doit être évaluée
comme une surface distincte : ne pas lui attribuer la qualification du chat web
ni celle de Codex par analogie.

L’installation web du plugin n’installe pas automatiquement Python ou AIR sur le poste.
Un IDE local peut exécuter l’installation documentée ; ChatGPT sans exécuteur local
doit guider l’utilisateur vers un installateur ou une commande vérifiée.

## Contrainte de publication ChatGPT

La [procédure OpenAI](https://developers.openai.com/plugins/deploy/submission)
accepte les skills autonomes et les plugins avec serveur MCP. Pour MCP, elle
demande une URL HTTPS publique stable, accessible mais authentifiée pour les données
privées. Une URL universelle est la voie habituelle. Les URL par workspace sous forme
de template nécessitent une approbation spécifique et une relation établie avec OpenAI.
Cela ne démontre pas que chaque utilisateur pourra saisir une URL arbitraire.

Le [guide de migration](https://developers.openai.com/plugins/guides/submit-claude-plugin)
demande de contacter OpenAI lorsque le fonctionnement central nécessite une exécution
locale. Une soumission « Skills only » n’importe pas la configuration MCP et ne permet
pas de référencer simplement une intégration existante. AIR ne peut donc pas promettre
un parcours d’annuaire universel avec son paquet de deux skills actuel.

Priorité : obtenir une réponse sur un connecteur par installation, avec pairing local
ou URL propre à l’entreprise. Préparer la demande suivante pour le canal OpenAI disponible
au développeur, sans prétendre disposer déjà d’un interlocuteur ou d’un accord :

> AIR conserve ses dossiers sur les postes des architectes. Nous souhaitons publier
> un plugin unique, avec un moteur libre installé séparément et une connexion MCP
> autorisée par chaque utilisateur. Quel parcours public supportez-vous : connexion
> locale, URL par installation ou template ? Quelles exigences d’authentification,
> de vérification de domaine et d’environnement de revue s’appliquent ?

Si aucun de ces parcours n’est accepté, proposer le mode IDE local et le mode ChatGPT
configuré individuellement lorsqu’il est disponible. Une passerelle universelle
opérée par AIR serait une autre architecture, avec coûts, identité, exploitation et
traitement des données en transit ; elle ne fait pas partie de la décision actuelle.
Un tunnel peut conserver le stockage local tout en ayant un intermédiaire réseau.

## Parcours cible d’un architecte

1. Télécharger une version publiée et ses empreintes depuis le projet officiel.
2. Faire installer cette version par l’IDE à partir du skill d’installation :
   environnement isolé, SQLite, identité locale, vérification doctor et sauvegarde.
3. Créer un référentiel et un dossier synthétique de prise en main ; choisir le
   référentiel à connecter et le rôle de l’agent. Ne pas lui donner implicitement
   tous les dossiers du freelance ni les mandats d’approbation.
4. Installer le plugin et connecter explicitement AIR selon le transport pris en
   charge. Pour ChatGPT distant, autoriser la connexion et la transmission des données
   nécessaires. Aucun secret n’est copié dans la conversation.
5. Demander un design logique, examiner les hypothèses, préparer les changements,
   vérifier les contraintes, simuler, puis produire les plans et livrables. Le moteur
   calcule les verdicts ; le modèle ne remplace pas un résultat absent par PASS.
6. Reprendre le dossier dans une nouvelle conversation depuis ses révisions et sa
   baseline, exporter les livrables, sauvegarder, puis pouvoir révoquer la connexion.

La réalisation et l’exécution métier du futur système ne font pas partie de ce parcours.
L’indisponibilité du poste doit produire un diagnostic clair, jamais une simulation
inventée. Les dossiers locaux ne sont ni fédérés ni synchronisés par cette distribution.

## Authenticité, confidentialité et licence

La [licence Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) permet usage,
modification et redistribution, y compris commerciaux, avec conservation de la licence
et des mentions requises. Elle n’impose pas de publier les dossiers produits par les
architectes et ne confère pas de droit général sur les marques. Le NOTICE du projet
exclut les données d’entreprise et ne relicencie pas le white paper original.

Le constructeur actuel inclut explicitement le PDF et parcourt notamment `docs`,
`fixtures` et `tests`. Ses exclusions de fichiers privés ne sont pas une revue de
publication. Préparer une liste de fichiers publics ; exclure le PDF tant que ses
conditions de redistribution ne sont pas définies, et remplacer les preuves privées
par des reçus publics expurgés. Vérifier aussi les licences des dépendances et les
mentions à joindre aux wheelhouses. Une SBOM de versions n’est pas cet audit de droits.

Conserver auteur et développeur Yannick Huchard, sources correspondant aux binaires,
version, empreintes et provenance. Prévoir une signature de release et sa vérification ;
ne pas présenter un hash placé à côté du ZIP comme une signature indépendante.

Pour le mode distant, suivre l’[authentification MCP OpenAI](https://developers.openai.com/plugins/build/auth) :
découverte de ressource protégée, consentement, code d’autorisation avec PKCE,
validation des jetons et contrôle des droits côté AIR. Le validateur OIDC actuel
est une brique réutilisable, pas la totalité de ce parcours. Choisir un composant
d’autorisation éprouvé ou une intégration acceptée ; ne pas imposer un IdP au mode local.
Le « No Auth » du tunnel de développement ne devient pas une configuration de serveur
public contenant des dossiers privés. Tester isolement, révocation et expiration.

Le stockage reste local, mais les extraits transmis à ChatGPT sont traités par le
fournisseur du modèle et éventuellement par le relais. Documenter ces flux et leur
rétention selon les services retenus ; ne pas promettre « aucune donnée ne quitte le poste ».

## Lots de livraison et critères de sortie

Ces lots D01–D06 complètent la roadmap ; ils ne clôturent pas P10–P14.

| Lot | Travaux | Critère vérifiable | Dépendances |
| --- | --- | --- | --- |
| D01 - source publique | Sélection du snapshot, revue secrets et matériaux, notices tierces, documentation publique, dépôt propre | Clone anonyme sans historique privé ; sources, licence et liste des exclusions vérifiées | Version de moteur choisie et revue de publication |
| D02 - installation autonome | Release publique versionnée, roue/source, installateur existant adapté aux URL publiques, catalogue de versions, guide débutant | Installation sur poste neuf sans accès développeur, réinstallation, sauvegarde/restauration et retour arrière reçus | D01 |
| D03 - connexion ChatGPT | Trancher la route avec OpenAI ; automatiser diagnostic et connexion supportés ; gérer expiration/reconnexion, catalogue et arrêt | Une autre identité ChatGPT accède seulement à son référentiel ; poste arrêté et jeton révoqué correctement refusés | Accord sur la route ; D02 pour recette publique |
| D04 - dossiers complets | Rejouer Asteria : trois dossiers distincts, préparation/dépôt autorisés, vérification, simulation, livrables et reprise | Preuves DEMO-METIER-1 sur la version distribuée ; UNKNOWN/VIOLATED/CONFLICTING et non-exécutés conservés | D02–D03 |
| D05 - annuaire | Identité développeur vérifiée, URL et auth si requises, environnement synthétique de revue, huit cas exécutés, scan, soumission puis publication | Accusé de soumission ; ensuite approbation et fiche publique vérifiée, états séparés | D03–D04 et accès portail |
| D06 - adoption | Aide FR/EN, politique de versions et migrations, support public/privé adapté, recette multiplateforme progressive | Un architecte externe installe et termine un dossier avec la seule documentation ; plateformes annoncées testées | D02–D05 pour parcours annuaire |

Première livraison recommandée : une distribution issue du moteur reçu rc9 avec les
mentions de licence ajoutées et une nouvelle vérification du paquet résultant, ou une
version ultérieure recevant sa propre qualification. Ne pas publier la branche
0.35.0.dev1 comme version stable par simple renommage. Commencer par Windows qualifié ;
macOS/Linux restent candidats jusqu’à recette dédiée. PyPI pourra simplifier la
distribution après vérification du nom, du contrôle du compte et du contenu ; aucun
`pip install air-engine` public fonctionnel n’est promis ici.

Les tests restent locaux pendant les lots. La CI manuelle demeure réservée à la
réception de la version de production complète, conformément à la décision utilisateur.

## État de cette évaluation

D01–D06 sont proposés, non reçus. Lecture du code, des preuves locales et des sources
officielles effectuée ; aucun test moteur relancé pour ce document. Aucun secret ni
historique privé publié, aucune modification de visibilité du moteur, aucune passerelle
créée. Le portail OpenAI est encore à la connexion ; soumission : **NOT_SUBMITTED**.
