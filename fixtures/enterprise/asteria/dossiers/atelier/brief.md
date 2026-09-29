# D02 — Maintenance connectée d’un atelier

Source fictive : visite du site pilote et atelier maintenance, automatisme, réseau,
sécurité et intégration. Date de référence : 21 septembre 2026. Aucune mesure réelle
de machine ou performance de modèle n’est fournie par ce scénario.

## Besoin et existant

Les techniciens utilisent une GMAO et des relevés manuels. Six des 36 machines du
site pilote peuvent fournir température et vibration via une passerelle. Le projet
vise un suivi de tendance et la préparation d’inspections. Il ne prétend pas prévoir
une panne avec une précision connue et ne remplace aucune protection de machine.

Le système collecte, horodate, qualifie et transmet les observations, puis propose
une inspection dans la GMAO après validation d’un technicien. La perte réseau doit
être visible. Une période sans télémétrie ne prouve pas l’absence d’anomalie.

## Périmètre, alternatives et contrats à construire

Comparer collecte locale avec export quotidien et collecte par passerelle vers une
plateforme centrale. Décrire les limites de fraîcheur, les zones réseau et le stockage
tampon. Aucun chemin d’écriture vers les automates ou actionneurs n’est autorisé
dans le pilote. Le responsable maintenance conserve la décision d’intervention.

Le contrat PublishMachineObservation précise machine, unité, instant de mesure,
instant de réception, identifiant de message et qualité. La répétition d’un message
ne crée pas deux observations ; un capteur silencieux produit une lacune explicite.
Le contrat ProposeInspection produit une proposition soumise à validation humaine,
jamais un arrêt de machine ou un ordre de travail approuvé implicitement.

## Parcours à démontrer

1. Modéliser acteurs humains, machines, passerelle, réseau et responsabilités.
2. Relier mesures, unités, fraîcheur et limites de validité aux contrats.
3. Jouer une expérience isolée avec données synthétiques et recette versionnée.
4. Montrer une perte de réseau et une donnée trop ancienne ; aucune conclusion
   « machine saine » ne doit être fabriquée à partir d’une absence de mesure.
5. Vérifier le décalage du pilote en semaines 5–8 et la revalidation des accès
   temporaires avant lancement.

## Inconnues et critères attendus

Les seuils d’alerte et les taux de faux positifs restent des hypothèses de simulation.
Un modèle non calibré ne justifie pas une décision de sécurité. La démonstration doit
montrer l’absence d’effet physique, les preuves utilisées et ce qui reste non testé.
Un compte collecteur expiré avant le lancement doit bloquer le nouveau départ,
même si un plan a été accepté antérieurement.

Besoin capacitaire synthétique : 2 ETP d’intégration pendant quatre semaines
consécutives, soit 8 ETP-semaines. La demande initiale porte sur les semaines 1–4 ;
une variante 5–8 est possible mais requiert une décision explicite et une revalidation.
