# Asteria Industrie — entreprise entièrement fictive

Toutes les données de ce jeu sont synthétiques. Le nom, les personnes, les chiffres,
les systèmes et les règles internes ne décrivent aucune entreprise réelle. Les
objectifs sont des hypothèses de démonstration, pas des résultats mesurés d’AIR.

Asteria fabrique et entretient des équipements de conditionnement pour des clients
professionnels. L’entreprise compte 1 200 salariés, trois sites de production,
80 techniciens itinérants et 35 gestionnaires de service après-vente. Environ
8 000 demandes SAV et 300 mouvements de collaborateurs ou prestataires sont traités
chaque année. L’atelier pilote possède 36 machines ; six sont retenues pour le
premier essai de collecte de télémétrie.

Le SI comprend un ERP, un outil de suivi des interventions, une GMAO, un SIRH,
un annuaire central, une passerelle d’API et une plateforme d’intégration. Les
échanges actuels mélangent interfaces applicatives, fichiers et opérations manuelles.
La qualité des données et les durées de traitement sont à mesurer ; les dossiers
ne supposent pas qu’un nom d’application ou une URL suffise à prouver son comportement.

## Acteurs et responsabilités

| Identité fictive | Rôle dans les exercices |
| --- | --- |
| Léa Morel, architecture entreprise | Cohérence des modèles et arbitrage d’architecture ; aucun mandat automatique de réservation |
| Karim Vidal, responsable intégration | Confirme l’offre de l’équipe et peut accepter une réservation dans son périmètre |
| Nora Simon, responsable SAV | Réception métier du portail et des parcours agents/clients |
| Éric Lambert, responsable maintenance | Réception du pilote atelier ; conserve l’autorité opérationnelle sur les machines |
| Inès Colin, responsable RH | Source faisant foi pour dates et statuts des salariés |
| Marc Petit, responsable IAM | Valide les droits et les règles de comptes ; contrôle les identités techniques |
| Salomé Roux, sécurité | Contribue aux contrôles et à la revue ; sa présence n’est pas une approbation automatique |

## Actifs et décisions communs

Les trois dossiers réutilisent un unique périmètre d’identité, référencé par le même
identifiant AIR et la même révision. Le portail doit fédérer les identités des
clients ; les collecteurs atelier utilisent des identités techniques ; le processus
RH pilote le cycle de vie des comptes internes. Ces populations ont des droits
distincts : partager une plateforme ne signifie pas partager les permissions.

La passerelle et les connecteurs ERP/GMAO/SIRH sont entretenus par une équipe de
quatre ingénieurs d’intégration. Cette offre de quatre équivalents temps plein est
**nette des obligations existantes**, limitée aux huit semaines de l’exercice.
Un ETP-semaine représente une unité de capacité sur une semaine de travail ; il
ne désigne ni le nombre total de salariés ni une durée de projet.

## Hypothèses communes de la recette

- Fenêtre : du lundi 5 octobre au lundi 30 novembre 2026, borne de fin exclue.
- Huit semaines de cinq jours de travail, sans congé ni jour férié dans ce calendrier
  synthétique. Ce choix n’est pas un calendrier légal d’un pays.
- Offre nette : 4 ETP d’intégration par semaine. Autres compétences non contraignantes
  dans ce seul exercice, à signaler comme simplification.
- Aucun gain de productivité agentique présumé ; aucune personne comptée deux fois.
- Le dossier atelier peut être décalé des semaines 1–4 vers 5–8 selon une variante
  à approuver. Le décalage n’est pas autorisé silencieusement par le solveur.
- Données clients, salariés et capteurs entièrement synthétiques. Aucun connecteur
  réel, message envoyé, réservation réelle ou commande de machine.

La même installation AIR SQLite et identité locale accueille les trois dossiers.
Les variantes PostgreSQL et OIDC appartiennent à une qualification technique
distincte ; elles ne sont pas des prérequis à la démonstration métier.
