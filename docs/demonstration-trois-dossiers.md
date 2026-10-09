# Recette de démonstration - trois dossiers d’une même entreprise

Rejeu du **27 septembre 2026**, moteur **0.34.0rc9** inchangé : `DEMO-METIER-1 PASS_SCOPED`.
Les trois dossiers et trois tests synthétiques signés passent ; SAV UNKNOWN, atelier VIOLATED,
identités CONFLICTING, portes BLOCKED et neuf cas métier originaux NOT_EXECUTED sont conservés.
Rapport privé `tmp/p07-followup-demo/report.json` ;
preuve complémentaire P07 (document historique ou livrable local non inclus).

Rejeu local **0.34.0rc9** : `DEMO-METIER-1 PASS_SCOPED`, trois dossiers et trois tests synthétiques
signés. SAV UNKNOWN, atelier VIOLATED, identités CONFLICTING ; portes BLOCKED et neuf scénarios
métier originaux NOT_EXECUTED. Rapport privé `tmp/p07-rc9-asteria/report.json` ;
preuve P07 (document historique ou livrable local non inclus). Ce rejeu ne reçoit pas les clients natifs.

Rejeu local **0.34.0rc8**, profil autonome par défaut : `DEMO-METIER-1 PASS_SCOPED`,
trois dossiers et trois tests synthétiques signés. SAV UNKNOWN, atelier VIOLATED,
identités CONFLICTING ; portes BLOCKED et neuf scénarios métier originaux NOT_EXECUTED.
Rapport privé : `tmp/p06-rc8-asteria/report.json` ;
preuve de réception P06 locale (document historique ou livrable local non inclus).

Rejeu local **0.34.0rc7** avec le profil `windows-job` du service actif :
`DEMO-METIER-1 PASS_SCOPED`, trois dossiers, HTTP/MCP et trois tests synthétiques signés.
SAV UNKNOWN, atelier VIOLATED, identités CONFLICTING ; portes BLOCKED et neuf scénarios métier
originaux NOT_EXECUTED. Rapport privé : `tmp/p06-rc7-asteria/report.json`.
La restauration chiffrée et les quatre calculs durables passent séparément ; l'arrêt des serveurs est vérifié.

Rejeu local **0.34.0rc6** : `DEMO-METIER-1 PASS_SCOPED` sur les trois dossiers, avec
`--qualify-external-proofs` ; rapport privé de recette `tmp/p06-rc6-asteria/report.json`.
SAV UNKNOWN, atelier VIOLATED, identités CONFLICTING, portes BLOCKED : les neuf scénarios métier
originaux restent NOT_EXECUTED. La recette de charge mixte P06 est séparée de cette réception métier.

Rejeu **0.34.0rc5 / 5531927** reçu sur Windows et Linux après ajout des limites HTTP.
Les trois parcours AIR et leurs tests synthétiques signés passent. SAV reste UNKNOWN, atelier VIOLATED,
identités CONFLICTING, portes BLOCKED ; les neuf cas métier ERP/atelier/IAM restent NOT_EXECUTED.
La nouvelle recette de requêtes lentes et de concurrence par identité est reçue séparément ; elle
ne constitue pas un test de capacité du groupe. Réception et empreintes (document historique ou livrable local non inclus).

Rejeu **0.34.0rc4 / 6ba234e** reçu sur Windows et Linux : les trois parcours AIR passent,
y compris leurs tests synthétiques signés. SAV reste UNKNOWN, atelier VIOLATED et identités CONFLICTING ;
les portes restent BLOCKED et les neuf cas ERP/atelier/IAM d'origine NOT_EXECUTED.
Les restaurations chiffrées de la recette d'exploitation passent séparément ; elles ne transforment
pas ces oracles métier en résultats calculés. Réception et empreintes (document historique ou livrable local non inclus).

Rejeu **0.34.0rc3 / b0b06dc** : les trois dossiers passent à nouveau sur Windows et Linux,
après les changements de journalisation et de sauvegarde P06. D01 SAV reste UNKNOWN (confirmation
ERP absente), D02 atelier VIOLATED (mesure périmée), D03 identités CONFLICTING (contradiction).
Les trois tests externes synthétiques supplémentaires passent ; les neuf scénarios métier originaux
restent NOT_EXECUTED. Réception P06 et empreintes (document historique ou livrable local non inclus).

Rejeu du 26 septembre 2026, candidate **0.34.0rc2**, commit **bbc421f** : les trois dossiers
ci-dessous passent sur Windows et Linux/Python 3.12, avec `--qualify-external-proofs`.
CLI/HTTP/MCP, refus hors périmètre, restauration et révocation sont exercés. D01 reste UNKNOWN,
D02 VIOLATED, D03 CONFLICTING ; les neuf cas métier originaux restent NOT_EXECUTED.
Les trois tests synthétiques externes supplémentaires sont exécutés et signés ; ils ne représentent
aucune connexion à l'ERP, à un atelier ou à l'IAM du groupe.
Rapports et empreintes de cette réception (document historique ou livrable local non inclus).

Rejeu du 25 septembre 2026 après les correctifs locaux P01/P02 : **DEMO-METIER-1 PASS_SCOPED**, trois dossiers
sur une installation SQLite isolée, via CLI/HTTP/MCP, avec restauration. Le SAV reste bloqué sur information
ERP absente, l'atelier sur mesure périmée et les identités sur contradiction. Les neuf cas métier ne sont pas
exécutés sur des systèmes réels. Statut et preuve de l'incrément (document historique ou livrable local non inclus).

Rejeu P03a du même jour : **PASS_SCOPED sur les trois dossiers**, avec `--qualify-design-proofs`.
Une inspection de conception supplémentaire par dossier devient `QUALIFIED_DESIGN_REVIEW` après avis
indépendant ; le critère VERIFICATION est MET pour cette portée de conception, avec zéro test runtime
vérifié. Révocation, nouvelle revue, parité CLI/HTTP/MCP, citation dans les livrables et restauration sont
passées. Les portes métier d'origine restent bloquées et les neuf scénarios restent NOT_EXECUTED.
Le rapport local est `tmp/production-p03/demo-asteria/report.json` ; la
preuve de réception conservée (document historique ou livrable local non inclus) en résume les résultats.

Réception P03/P04 avec `--qualify-external-proofs` : **PASS_SCOPED** pour les trois dossiers.
Chaque dossier ajoute un test unittest fictif, exécuté dans un processus externe, signé puis importé et
revu indépendamment. La signature altérée est refusée, l'import identique est idempotent, CLI/HTTP/MCP
rendent la même qualification et la révocation de la clé fait passer le compteur vérifié de 1 à 0.

| Dossier | Test supplémentaire exécuté | Porte métier d'origine |
| --- | --- | --- |
| D01 SAV | Idempotence du dépôt et attente de confirmation ERP | UNKNOWN, toujours bloquée |
| D02 atelier | Rejet d'une mesure périmée ou de mauvaise unité | VIOLATED, toujours bloquée |
| D03 identités | Expiration exclusive et sponsor obligatoire | CONFLICTING, toujours bloquée |

Les neuf scénarios métier d'origine restent NOT_EXECUTED. Après restauration, les reçus historiques sont
conservés, mais la nouvelle politique invalide leur qualification effective. Cette recette corrige le
contrôle P03a précédent qui réutilisait directement l'ancienne politique en mémoire : son assertion
`restored_same_qualification` ne décrit pas une qualification effective de l'installation restaurée.
Rapport local : `tmp/production-p03-p04/demo-final/report.json` ;
réception et empreintes (document historique ou livrable local non inclus).

Demande utilisateur enregistrée le 19 septembre 2026. Dès que le niveau de réception
DEMO-METIER-1 ci-dessous est atteint, exécuter et présenter les trois dossiers au
cours du développement, sans attendre la fin de tous les lots ni une nouvelle demande.
Cette exigence fait partie de L00, L06, L07 et L17. Aucune tâche de surveillance
en arrière-plan n’est nécessaire : la réception accompagne les incréments du produit.

## Entreprise et dossiers

[Asteria Industrie](../fixtures/enterprise/asteria/company.md) est entièrement fictive :
1 200 salariés, trois sites industriels et une activité de maintenance chez ses
clients. Les sources, chiffres, personnes et systèmes du jeu sont synthétiques.

| Dossier | Problème et collaboration | Ce que la démonstration devra mettre en évidence |
| --- | --- | --- |
| [D01 - Portail SAV](../fixtures/enterprise/asteria/dossiers/sav/brief.md) | Clients, gestionnaires, techniciens, ERP et intégration | Besoin → contrat → construction ; doublon, accès d’un autre client, indisponibilité ERP ; dépôt distinct d’une décision de garantie |
| [D02 - Maintenance connectée](../fixtures/enterprise/asteria/dossiers/atelier/brief.md) | Maintenance, automatismes, réseau industriel, données et sécurité | Composants humains/physiques ; unités, fraîcheur et absence de données ; proposition d’inspection sans commande de machine |
| [D03 - Cycle de vie des accès](../fixtures/enterprise/asteria/dossiers/identites/brief.md) | RH, sponsors de prestataires, managers, IAM et support | Sources faisant foi ; droits et temporalité ; proposition/approbation/exécution séparées ; propagation partielle et effets d’une règle commune |

Les trois dossiers utilisent **la même installation AIR**, le même référentiel
d’identité et la même équipe d’intégration. Chaque dossier a ses sources, son
périmètre et ses responsabilités. Les actifs partagés ont un identifiant unique,
référencé à une révision précise. Une modification commune doit permettre de
retrouver les dossiers concernés, sans dupliquer ou écraser l’actif partagé.

## Ce qui constitue un niveau acceptable

DEMO-METIER-1 est une première démonstration de conception traçable. Elle exige
un parcours réellement exécuté pour les trois dossiers, et pas seulement un jeu
de données chargé ou une présentation générée.

| Critère | Résultat attendu et preuve |
| --- | --- |
| M1-BASELINE | Références typées et fermées ; baseline conservée et relue avec les mêmes digests ; référence absente refusée |
| M1-KNOWLEDGE | Sources/preuves/assertions/hypothèses/inconnues distinctes ; une preuve obligatoire absente ne devient pas une validation réussie |
| M1-CONTRACT | Au moins une exigence, une fonction, un contrat et une unité de construction reliés dans chaque dossier |
| M1-CHANGE | Changement proposé, diff explicable et nouvelle version ; impact d’une évolution de l’identité sur les trois dossiers, avec périmètre d’applicabilité |
| M1-AUTHORITY | Lecture/écriture selon le mandat ; lecture interdite et approbation auto-déclarée refusées ; la simple proposition n’autorise aucune exécution |
| M1-VIEW | Vue lisible pour métier et ingénierie, tirée du modèle et exposant preuves, inconnues, décisions et contrôles non exécutés ; un export HTML suffit pour ce premier jalon |
| M1-INSTALL | Installation SQLite/local neuve depuis doc + skill ; reprise du dossier sans historique de conversation ; restauration des révisions vérifiée |

Un critère requis NOT_EXECUTED, UNKNOWN ou en échec empêche de déclarer le jalon
réceptionné. Les identifiants, versions, entrées, sorties, preuves de tests et
limitations doivent figurer dans le rapport. Aucun statut ne doit être déduit de
la seule présence d’une route API, d’un fichier de schéma ou d’un bouton.

## Déroulé de la première démonstration

1. Installer une instance isolée SQLite/local et ouvrir le contexte d’entreprise.
2. Charger les trois dossiers et montrer les références uniques aux actifs communs.
3. Pour chaque dossier : lire les sources, expliciter les inconnues, proposer le
   modèle, exécuter les contrôles disponibles et montrer la vue de construction.
4. Injecter une exception propre au dossier : preuve ERP manquante, mesure atelier
   périmée, ou approbation de droits auto-déclarée. Montrer diagnostic et effet sur
   la porte concernée, sans produire de preuve artificielle pour rendre le test vert.
5. Faire évoluer la politique d’identité dans une proposition versionnée ; comparer
   l’avant/après et les impacts applicables. Conserver les anciennes baselines.
6. Changer d’acteur, vérifier les accès interdits, puis reprendre depuis les artefacts
   avec un nouveau contexte d’IDE. Le client ne dépend pas du texte des conversations.
7. Restaurer une copie isolée et comparer les digests. Produire un rapport des
   parcours réussis, refus attendus, limites et fonctionnalités restant à construire.

Les sources peuvent fournir les entrées d’une simulation ; elles ne prouvent pas
qu’un ERP réel accepte une demande ni qu’une machine répond à un seuil. Les premiers
tests sont déterministes et synthétiques. Les recettes plus avancées suivent le
jalon ci-dessous au fur et à mesure de leur implémentation.

## Deuxième démonstration : portefeuille, simulation et engagements

La même entreprise sert à DEMO-PORTEFEUILLE-2 lorsque L09–L14 permettent ces effets.
La fenêtre synthétique contient huit semaines, du 5 octobre au 30 novembre 2026,
fin exclue. L’offre nette est de quatre ETP d’intégration chaque semaine.

| Demande | Semaines 1–4 | Semaines 5–8 | Total |
| --- | ---: | ---: | ---: |
| D01 SAV | 2 ETP/semaine | 0 | 8 ETP-semaines |
| D02 atelier, proposition initiale | 2 ETP/semaine | 0 | 8 ETP-semaines |
| D03 identités | 1 ETP/semaine | 0 | 4 ETP-semaines |
| Total initial | **5 ETP/semaine** | 0 | 20 ETP-semaines |

Résultat attendu : dépassement d’un ETP chacune des quatre premières semaines,
soit quatre ETP-semaines. Une variante décalant D02 en semaines 5–8 donne une charge
de trois puis deux ETP, compatible avec cette seule contrainte capacitaire. La
variante reste à qualifier et à approuver : faisabilité n’est ni admission ni
autorisation de lancement. Ces nombres définissent l’oracle d’essai ; la tranche 06 les retrouve désormais par
calcul indépendant, avec preuves dans verification-calculs.json.

Exécuter ensuite les tests d’admissions concurrentes sans double réservation, de
source capacitaire indisponible, de compte collecteur expiré avant activation,
de panne partielle et de restauration. Rejouer l’expérience atelier sans action
physique. Afficher les simplifications du calendrier et des autres ressources.
L’ajout de PostgreSQL/OIDC ne doit pas être requis pour exécuter ces scénarios.

## Préparation déjà exécutable

Le [manifeste](../fixtures/enterprise/asteria/manifest.json) conserve dossiers,
références communes, critères et oracle capacitaire. Les trois briefs sont liés
à des Source par leur digest SHA-256. Neuf objets de cadrage compatibles avec le
bootstrap sont fournis : trois communs et deux par dossier.

Précontrôle Windows, depuis la racine :

```bat
.venv\Scripts\python.exe scripts\check_enterprise_fixture.py
```

Sous Unix : `.venv/bin/python scripts/check_enterprise_fixture.py`.
Le précontrôle utilise une SQLite temporaire isolée, vérifie sources, cohérence du
jeu, stockage, digests et répétition idempotente, puis écrit
tmp/demo-asteria/preflight.json. Il ne modifie pas l’instance .air.

**État historique du précontrôle bootstrap : jeux préparés, démonstration alors NOT_READY.** Le résultat
bootstrap PASS n’est pas un PASS des critères M1. Le rapport expose explicitement
les contrôles non exécutés. Les tests HTTP de coexistence des trois dossiers sont
dans tests/test_enterprise_fixture.py. Le rapport de cette étape est conservé dans
verification-trois-dossiers.json (document historique ou livrable local non inclus).


## Avancement de la tranche 02

Les trois dossiers possèdent désormais un fichier foundation.json et une demande baseline-request.json. Le parcours scripts/demo_foundation.py a vérifié neuf membres par dossier, AIR-V003 dans ce sous-profil, export/reconstruction à digest identique, proposition de révision et répétition idempotente, sans modification de la baseline d’origine. Le même parcours est testé via CLI/HTTP.

M1-BASELINE est vérifié pour les six types pris en charge. M1-KNOWLEDGE/M1-CHANGE restent partiels ; M1-CONTRACT, droits fins de M1-AUTHORITY, impacts et M1-VIEW restent à implémenter. Le jalon métier reste NOT_READY. Voir [le contrat livré](lot-connaissance-baselines.md) et les preuves (document historique ou livrable local non inclus).

## Avancement de la tranche 03

Le parcours `scripts/demo_validation.py` exécute les portes des trois dossiers dans
une même SQLite isolée. D01 produit UNKNOWN pour une confirmation ERP absente, D02
VIOLATED pour une mesure trop ancienne et D03 CONFLICTING pour des informations
incompatibles. Les variantes d’entrées corrigées satisfont ces prédicats, mais les
portes restent BLOCKED : inconnues de baseline et revue humaine obligatoire ouvertes.
Les résultats sont rejouables à digest identique et vérifiés via CLI/HTTP réel.

M1-KNOWLEDGE progresse : absence de preuve et contradiction ne deviennent pas une
validation réussie. La qualification humaine demeure à réaliser. M1-CONTRACT,
impacts, droits fins et M1-VIEW restent ouverts : DEMO-METIER-1 demeure NOT_READY.
Les oracles de portefeuille restent distincts du simple exemple de comparaison
AIR-Expr ; aucun planner n’a été implémenté. Voir les preuves (document historique ou livrable local non inclus).

## Avancement de la tranche 04

Chaque dossier possède construction.json et construction-baseline-request.json :
24 objets, une chaîne exigence/fonction/contrat/unité et trois scénarios de réception
décrits. scripts/demo_construction.py vérifie la structure, la restauration, un
contrat incomplet et une proposition d’estimation. Les empreintes historiques sont
préservées ; les commandes sont également vérifiées via CLI/HTTP réel.

M1-CONTRACT est vérifié dans air.construction/0.4. Les VerificationCase restent
NOT_EXECUTED/UNKNOWN et les portes BLOCKED : les tests AIR ne prouvent pas le
comportement d’un ERP, d’une machine ou d’IAM. Impacts entre dossiers, vues, droits
fins et revue demeurent nécessaires. DEMO-METIER-1 reste NOT_READY.
Voir [le contrat](lot-construction.md) et les preuves (document historique ou livrable local non inclus).

## Réception de la tranche 05

DEMO-METIER-1 est PASS_SCOPED : scripts/demo_metier.py a exécuté les sept critères
par HTTP/MCP sur une installation SQLite/local neuve, avec trois architectes, un
relecteur indépendant, accès interdits, refus des auto-approbations, propositions,
diff, impact commun, vues HTML et restauration à empreintes identiques.

Rejouer : `python scripts/demo_metier.py --fresh-environment` avec Python de .venv.
Les artefacts sont dans tmp/demo-asteria/metier ; les preuves durables dans
verification-collaboration.json (document historique ou livrable local non inclus).
Cette réception concerne la conception traçable AIR ; les cas métier restent
NOT_EXECUTED, les portes de construction BLOCKED, le portefeuille non réceptionné.

## Calculs de la tranche 06

Le moteur planning produit effectivement le déficit initial de 4 ETP-semaines, puis
la variante de 3 et 2 ETP sous les contraintes déclarées. Les scénarios finis des
trois dossiers sont simulés dans AIR-Expr (11 cas, classe ILLUSTRATIVE) ; aucune
exécution ERP, machine ou IAM. Les cas de vérification du système réel restent ouverts.
Voir les preuves calculées (document historique ou livrable local non inclus).
DEMO-PORTEFEUILLE-2 demeure NOT_READY jusqu’aux tests d’engagement et d’activation.

## Réception de la tranche 10

DEMO-PORTEFEUILLE-2 est PASS_SCOPED pour le binding central de ressources humaines : scripts/demo_admission.py exécute offres habilitées, revue indépendante, refus des 5 ETP pour 4 disponibles, concurrence de trois admissions, libérations explicites avant activation, puis réservation collective de 3 et 2 ETP. Une interruption réelle du client après commit et un redémarrage du serveur permettent de vérifier le replay sans nouvelle réservation.

Le SAV reçoit une autorisation locale dans une fenêtre issue de l’horloge réelle du serveur. Une offre indisponible puis une identité de déclarant révoquée bloquent le lancement suivant ; les réservations du travail activé restent conservées et sont restaurées à l’identique. L’expiration de l’identité est contrôlée avec une horloge de test distincte, sans modifier le résultat HTTP. La fenêtre d’essai est translatée par rapport aux dates de l’oracle ; les quantités et les huit semaines sont conservées.

Les onze expériences illustratives sont rejouées. Cette réception ne couvre pas la simulation calibrée, les transactions entre autorités distantes, les systèmes ERP/atelier/IAM réels ni la clôture et le renouvellement des épisodes, qui constituent le contrat suivant. Rapport : tmp/demo-asteria/admission.json ; vue : tmp/demo-asteria/admission.html.

## Cycle des engagements de la tranche 11

La recette scripts/demo_lifecycle.py est PASS_SCOPED en 0.11 : renouvellement sous nouvelle politique et nouvelle identité du déclarant, conservation des douze lignes de réservation, activation suivante, deux clôtures déclarées et revues indépendamment, maintien des épisodes ouverts, puis libération explicite. La réservation atelier jamais activée est annulée ; ce travail n’est pas déclaré achevé. Les états et reçus restent identiques après restauration.

La vue tmp/demo-asteria/lifecycle.html a été inspectée. Les 226 tests passent sur SQLite et PostgreSQL 18.6 ; M1 est également rejoué. Voir docs/traceability/verification-lifecycle.json.

## Observations et dérive - tranche 12

scripts/demo_runtime.py prolonge les trois dossiers dans une même installation isolée : confirmation ERP absente → VIOLATED, mesure atelier de 540 secondes au seuil de 300 → VIOLATED, état IAM contradictoire → CONFLICTING. Une fraîcheur exigée de 30 secondes produit UNKNOWN. Les données sont fictives et DRAFT, la couverture PARTIAL.

Les nouvelles baselines contiennent chacune 28 objets ; les anciennes restent immuables. Ingestion idempotente, refus transversal, rejeu CLI/HTTP/MCP et restauration identique sont vérifiés. La vue runtime.html a été inspectée. 236 tests passent sur SQLite et PostgreSQL 18.6. Les recettes M1 et renouvellement/clôture sont rejouées. Voir traceability/verification-runtime.json.

## Contributions et décisions - tranche 13

scripts/demo_collaboration.py prolonge les trois observations par une question d’un contributeur, une décision d’un architecte distinct et une résolution documentée. Les baselines de traitement contiennent 30 objets ; les versions antérieures sont conservées. Dépôt attribué, usurpation refusée, replay CLI/HTTP/MCP et restauration identique sont vérifiés. La vue collaboration.html a été inspectée. 243 tests passent sur SQLite et PostgreSQL 18.6 ; M1 est rejoué. Voir traceability/verification-design-collaboration.json.

## Workbench portable - tranche 14

Les trois HTML autonomes sont générés par scripts/demo_workbench.py. Une recette Edge/Chromium vérifie recherche, filtrage, liens, clavier, mobile et préparation de contributions. Le texte hostile est inerte, la lecture seule est respectée, la liste sans JavaScript reste disponible et le réseau est bloqué par CSP. Les trois JSON téléchargés ont ensuite été déposés par CLI, rejoués sans doublon et restaurés avec des reçus identiques.

247 tests passent sur SQLite et PostgreSQL 18.6 ; M1 est rejoué. Voir traceability/verification-workbench.json. Cette réception porte sur un export hors ligne et des dépôts DRAFT ; elle n’autorise aucune opération sur un système métier.

## Tranche 24 - replay des états

scripts/demo_state_replay.py reprend les trois baselines de données dans une copie isolée. Chaque dossier contient 69 objets et une machine explicite. Trois replays par dossier vérifient état nominal, exception et refus de revue indépendante.

| Dossier | Exception calculée | État conservé ou atteint |
| --- | --- | --- |
| D01 SAV | UNKNOWN, confirmation ERP non établie | PENDING, transition non appliquée |
| D02 atelier | INPUT_EXHAUSTED, âge 540 s supérieur au seuil 300 s | WAITING, transition d’attente appliquée |
| D03 IAM | CONFLICTING, cohérence d’identité contradictoire | PENDING, transition non appliquée |

Les cas nominaux atteignent READY ; une revue refusée produit INVARIANT_VIOLATED dans chacun des trois dossiers et conserve PENDING. L’accès transverse est refusé. Les rapports CLI/API/MCP et ceux relus après restauration sont identiques. Les effets restent déclaratifs et les neuf VerificationCase métier originaux restent NOT_EXECUTED. Preuves : traceability/verification-state-replay.json.

## Tranche 25 - politiques et contrôles

scripts/demo_policies.py reprend les trois baselines d’états et les porte à 80 objets. Chaque dossier ajoute procédure fictive, contrainte, contrôle, obligation, politique, risque, deux cas de revue décrits, décision d’applicabilité, décision de proposition et dérogation DRAFT. La date du calcul est le 6 octobre 2026, dans la fenêtre de validité fictive.

Les trois cas nominaux satisfont la condition déclarée. Les exceptions restent UNKNOWN pour le SAV, VIOLATED pour la fraîcheur atelier et CONFLICTING pour IAM, avec un blocage hard chacun. Les dérogations restent NOT_VERIFIED/applied=false. Les six diagnostics CLI/API/MCP sont identiques après restauration ; la lecture transverse est refusée. Les cas de vérification métier et les nouvelles revues décrites ne sont pas exécutés par ce diagnostic. Preuves : traceability/verification-policies.json.

## Tranche 26 - blocs, ports et flux

scripts/demo_architecture.py reprend les trois dossiers de gouvernance et les porte à 88 objets. Chaque dossier décrit un bloc fournisseur et un bloc consommateur, leurs deux ports exacts, un binding HTTP/JSON, un flux, un livrable attendu et une lacune d’implémentation.

Les routes proposées sont /claims pour le SAV, /inspections pour l’atelier et /access-revocation-proposals pour IAM. Les endpoints sous asteria.invalid restent des déclarations et ne sont pas contactés. Les rapports CLI/API/MCP et après restauration sont identiques ; l’accès transverse est refusé. La cohérence structurelle des contrats ne prouve pas une implémentation, une sécurité externe ou une compatibilité de comportement. Preuves : traceability/verification-architecture.json.
