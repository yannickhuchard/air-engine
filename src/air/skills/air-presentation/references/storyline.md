# Fil narratif d'une architecture de solution

Structure SCQA (situation, complication, question, réponse), la réponse en tête, puis où l'on en est. Les sections
vont du métier au système, puis à la réalisation, aux finances, aux risques, enfin aux décisions. Chaque ligne donne
le titre type (celui que compile AIR, écrit pour un dirigeant non expert), le visuel et les objets AIR qui le fondent.

| # | Section | Titre type | Visuel | Sources AIR |
|---|---|---|---|---|
| 1 | Couverture | Nom du programme, client, prestataire | page de titre | Baseline |
| 2 | Synthèse | « Fin visée le 30 juillet 2027 pour 459 k€ d'investissement ; le lancement attend trois validations, déjà identifiées » | 4 blocs (ce que nous construisons, comment, quand et combien, où nous en sommes) + décision demandée | Goal, ConstructionUnit, ArchitectureBlock, Roadmap, CostItem, porte |
| 3 | Où nous en sommes | « Avant de lancer les travaux, trois validations doivent encore être obtenues ; chacune est identifiée » | tableau projet, prêt à lancer, ce qu'il reste à faire ; ce que cela signifie | porte air.readiness-gate |
| 4 | Contexte | « Le programme poursuit 6 objectifs mesurables » | tableau objectif, résultat attendu, cible | Goal |
| 5 | Enjeux | « Sans ce programme, 8 difficultés rencontrées par les utilisateurs et 9 risques identifiés resteraient sans réponse » | deux colonnes : difficultés, risques principaux avec leur niveau | CustomerJourney, RiskAssessment |
| 6 | Métier | « La valeur est créée dans 4 grands enchaînements d'activités, de la demande du client jusqu'au résultat » | flèches d'étapes avec délais | ValueStream |
| 7 | Métier | « Le programme couvre 13 savoir-faire de l'entreprise, répartis en 9 domaines de responsabilité » | grille par domaine | Capability, Domain |
| 8 | Métier | « 7 parcours utilisateurs ont été décrits étape par étape, avec leurs difficultés » | tableau parcours, utilisateur, canaux | CustomerJourney |
| 9 | Solution | « La solution est découpée en 10 composants indépendants, chacun responsable de ses propres données » | schéma des composants ; ce que cela signifie | ArchitectureBlock, SemanticContract |
| 10 | Solution | « Les informations circulent en temps réel entre les composants ; les temps de réponse visés sont atteints en simulation et devront être confirmés par des mesures » | puces ; ce que cela signifie | Event, VerificationRun |
| 11 | Solution | « Les 12 parcours d'utilisation testés sur plan fonctionnent ; les tests sur le logiciel suivront sa construction » | tableau par application ; fonctions pas encore couvertes | NavigationMap, AcceptanceScenario |
| 12 | Solution | « Les 19 exigences de sécurité et de conformité ont chacune une solution prévue et un responsable ; aucune n'est encore vérifiée » | tableau exigence, mise en œuvre, responsable | Control, QualityRequirement, ComplianceMapping |
| 13 | Solution | « Les choix techniques reposent sur 16 technologies et 12 décisions documentées » (version contrat) | technologies retenues, décisions | Technology, Decision |
| 14 | Réalisation | « 6 scénarios de réalisation ont été comparés ; le scénario recommandé pour chaque projet s'appuie sur l'IA et fait gagner jusqu'à 1,5 mois » | tableau par projet : durée, gain de temps, coût, avis ; recommandation chiffrée | Roadmap, DeliveryEstimate |
| 15 | Réalisation | « Fin des travaux visée le 30 juillet 2027 ; la date dépend surtout de l'avancement du projet « Plateforme de gestion » » | gantt ; enchaînement qui fixe la date de fin ; liens entre projets | Roadmap |
| 16 | Réalisation | « Les outils d'IA pourraient réduire la charge de travail d'environ 36 % (157 jours), pour 5 029 € d'abonnements ; ce gain sera mesuré dès les premiers mois » | histogramme sans IA, avec IA ; ce que cela signifie | DeliveryEstimate, AgenticToolPlan |
| 17 | Réalisation | « Chaque décision a un seul responsable : 17 activités, 8 décideurs » (version contrat) | tableau activité, moment, qui décide | RaciAssignment, Role |
| 18 | Finances | « Un investissement de 459 k€ (556 k€ sans IA), puis 1,24 M€ par an de fonctionnement, dont 878 k€ de personnel » | histogramme investissement, fonctionnement | CostItem |
| 19 | Risques | « 9 risques ont été évalués ; 2 des plus importants n'ont pas encore de plan d'action » | carte de chaleur + principaux risques avec leur niveau | RiskAssessment |
| 20 | Décision | « Trois décisions sont attendues aujourd'hui » | liste numérotée + périmètre contractuel | Roadmap, porte |
| 21 | Annexe | « Chaque chiffre de ce document provient d'une version datée et vérifiable du dossier » | versions par projet et empreinte de contrôle | Baseline |

## Écrire un bon titre

- Une phrase complète en mots de métier : sujet, verbe, chiffre, conséquence.
- Au plus deux lignes ; pas de sigle non défini ; pas de point final.
- Le chiffre du titre est visible sur la diapositive.
- Le titre porte la nuance quand elle change le sens : date visée, objectif atteint en simulation, solution prévue
  plutôt qu'en place, parcours testé sur plan plutôt que recette.

## Du deck à l'histoire orale

Les notes de l'orateur (touche `n`) donnent la phrase de transition et la limite à ne pas franchir à l'oral
(par exemple : une simulation montre que l'objectif est atteignable ; elle ne prouve pas le fonctionnement réel).
