# Lot D : rechercher les erreurs et préparer les changements

Le lot D complète les contrôles existants par deux services en lecture seule.
La recherche comportementale explore un domaine fini déclaré par l'architecte,
rejoue des séquences sur la machine à états ou des échanges sur un contrat,
et restitue une entrée reproductible qui contredit l'attente déclarée.
L'analyse des preuves compare deux baselines exactes et montre les dépendances
modifiées, les chemins concernés et les vérifications à reprendre.

## Parcours de travail et réception prévue

1. Choisir la baseline, la machine ou la spécification exacte.
2. Déclarer les contextes ou échanges candidats et l'attente. Les valeurs
   proviennent du dossier, de limites métier ou de données sourcées.
3. Explorer les séquences par longueur croissante. Lire les contre-exemples,
   inconnues et limites, puis corriger le design dans une nouvelle révision.
4. Comparer ancienne et nouvelle baselines. Préparer les relectures et rejeux
   ciblés depuis les dépendances déclarées ; les preuves historiques sont conservées.
5. Régénérer le site. Sa page de vérification présente les preuves déclarées,
   leurs résultats et les changements depuis les parents explicitement enregistrés.

Réception : contre-exemple reproductible, refus attendu distinct d'une erreur,
UNKNOWN et budget incomplet distincts d'un succès, dépendances indirectes et
cycles, changement sans impact déclaré, contrôle des droits et digests,
services identiques CLI/API/MCP, site lisible et trois parcours Asteria locaux.
Les résultats des tests seront consignés après leur exécution.

## Limites de qualification

Le domaine est fini et fourni explicitement. Une absence de contre-exemple ne
prouve pas l'architecture entière, ses délais, sa sécurité ou le logiciel futur.
Les contextes contradictoires sont inconclusifs ; deux transitions activables
avec un contexte connu constituent une ambiguïté du modèle.
Les anciens avis restent valables pour leur baseline historique selon leurs
propres droits, expiration et révocation. Aucun avis ne migre automatiquement.
L'absence d'impact déclaré reste à relire pour une nouvelle baseline : les liens
manquants et dépendances externes empêchent de garantir une indépendance réelle.
Aucun service de ce lot n'exécute d'effet métier, ne déploie ou n'approuve un dossier.

## CLI et MCP

`behavior-states requete.json` et `air_search_state_counterexamples` utilisent
baseline, machine, initial_context, alphabet, max_depth (1 à 4) et max_trials
(1 à 64). Chaque symbole de l'alphabet contient trigger et context typé AIR-Expr.
Les séquences sont explorées par longueur croissante, y compris la séquence vide
par défaut. allowed_outcomes précise les fins acceptables. Les refus attendus
ne sont pas des erreurs ; les invariants violés et ambiguïtés connues le sont.
Le premier contre-exemple est le plus court parmi les séquences testées, sans
minimisation des valeurs. Le rapport est limité à 1 Mio ; chaque rejeu conserve
ses limites AIR-Expr. L'alphabet complet est validé avant l'exploration.

`behavior-interfaces requete.json` et `air_search_interface_counterexamples`
prennent baseline, specification, operation et jusqu'à 64 exchanges. Chaque
échange a request, response facultative et expected PASS ou FAIL. scope vaut
EXCHANGE par défaut ; REQUEST_ONLY limite volontairement le contrôle à l'entrée.
Sans réponse, un échange complet qui passe les préconditions reste inconclusif.
Une entrée invalide attendue n'est pas un contre-exemple. Le service ne génère
pas des valeurs inconnues et n'appelle aucun fournisseur.

`evidence-impact requete.json` et `air_assess_evidence_impact` prennent before
et after, deux pins exacts. targets sélectionne facultativement jusqu'à 256
VerificationCase, VerificationRun, SimulationScenario ou Evidence source.
Les références transitives sont suivies, avec chemins et digests. Un profil
modifié affecte tous les cas sélectionnés. Les références hors baseline restent
explicites. La traversée est limitée à 100 000 nœuds visités, 64 pas par chemin,
4 Mio de résultats et 32 Mio par snapshot. Une limite produit un refus explicite.

Les rapports sont déterministes et téléchargeables. On peut conserver leurs
octets avec artifact-upload puis relier le rapport à une preuve du dossier.
Leur présence ne qualifie pas à elle seule un VerificationRun ou une revue.
`verification.html` et `verification-impact.json` sont générés avec le site.
La page compare au plus huit baselines parentes déclarées, jamais la dernière
révision trouvée implicitement. Les lectures sans registre signalent une
comparaison non exécutée. Le guide REVIEW propose le contrôle d'impact exact.

La page reprend le branding du dossier et ses styles responsive. Son parcours
de lecture commence par les résultats déclarés, puis les changements : nom du
cas, état lisible, détail ouvrable au clavier et chemin de dépendance. Les URN
restent dans les détails. Aucun bouton du site ne donne un avis ou une approbation.
Les observations navigateur sont des contrôles techniques, sans avis UX humain.

## Réception et distribution

Le [reçu technique](traceability/lot-d-2026-10-11.json) conserve les tests,
la recette CLI/MCP, le navigateur et les trois dossiers Asteria. Le
[reçu de publication](traceability/lot-d-publication-2026-10-11.json) ajoute
installation, restauration, upgrade, exécution avec le wheel et contrôle des
assets publics. La recherche d'états conserve aussi la limite de 1 Mio du
snapshot de son moteur de rejeu ; les autres analyses ont leurs budgets propres.
Le retraitement d'un ancien avis pour une nouvelle baseline reste une décision
explicite, distincte de l'absence d'impact sur les références déclarées.
