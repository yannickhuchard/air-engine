# Lire le dossier dans un ordre qui aide à décider et à construire

## Revue avant réalisation

La navigation actuelle additionne des raccourcis avant cinq groupes thématiques.
La synthèse arrive après les News ; les données, l'organisation et la finance
n'ont pas le même niveau de classement. Le dernier groupe contient seize sujets.
Plusieurs vues n'indiquent pas leur lien actif. Le lecteur peut trouver une page
sans comprendre sa place dans le raisonnement d'ensemble.

Le métier demande pourquoi changer et comment ses activités seront affectées.
Le COMEX examine la valeur, les moyens, les arbitrages et les risques.
Les constructeurs cherchent les mécanismes, contrats, responsabilités,
dépendances et critères de réception. Le même dossier doit permettre ces lectures
sans dupliquer son contenu ni filtrer les données selon le public.

## Parti pris UX/UI

La colonne de gauche est une table des matières progressive. Elle offre d'abord
la vue d'ensemble, la synthèse management et le récit ; trois accès de lecture
permettent ensuite de présenter au métier, d'arbitrer au COMEX ou de préparer
la transmission aux équipes. Les sujets sont rangés une seule fois par dimension
dans sept parties. Les identifiants et URL des 38 livrables restent stables.

1. **Cadrer la demande** : intention, valeur, capacités, parties prenantes et finance.
2. **Décrire les usages** : parcours clients, interfaces, processus et règles métier.
3. **Concevoir la solution** : principes, décisions, composants et interactions.
4. **Structurer les données** : sémantique, modèle logique et modèle physique.
5. **Maîtriser la qualité et les risques** : qualité, sécurité, contrôles, hypothèses et écarts.
6. **Préparer la construction** : technologies, environnements, organisation et trajectoire.
7. **Vérifier et piloter** : traçabilité, scénarios, préparation, livraison et suivi.

Chaque partie possède une page d'entrée et des dimensions nommées. Le groupe
contenant la page active s'ouvre ; les autres restent repliables. Un repère dans
le contenu situe la partie et la dimension, avec précédent et suivant entre
parties. La même séquence apparaît sur l'accueil.

```text
Vue d'ensemble / Synthèse / Récit
Présenter au métier / Arbitrer au COMEX / Transmettre aux équipes

1 Cadrer la demande
  Valeur et périmètre
    Objectifs / chaîne de valeur / capacités
  Parties prenantes
    Carte / rôles
  Finance
    Synthèse détaillée / postes et sources
2 Décrire les usages
  Expérience client
  Processus et règles métier
...
7 Vérifier et piloter
  Vérification et réception
  Suivi de la transformation

Outils, autres lecteurs et sources
```

Palette : encre #17333c, bleu #17687c, fond #f1f6f7, ligne #d0dfe4, papier #ffffff.
Police et couleurs héritent du branding du dossier. Les numéros expriment l'ordre
de lecture ; les dimensions sont des sous-titres sobres. Un repère de sélection
et un libellé accompagnent la couleur. Les cibles tactiles font au moins 44 pixels.
Sur mobile, le même sommaire est accessible par un bouton natif de dépliage.

## Critique et limites

Une navigation par types de l'ontologie aiderait surtout les experts déjà
familiers d'AIR. Une navigation uniquement par métier et équipe créerait des
rubriques répétées. Le parcours principal est donc partagé ; les lectures par
public restent des raccourcis vers les vues existantes. La finance est lisible
dès le cadrage et se réexamine après les choix de conception.

Ces parties constituent un ordre d'explication, pas des gates ni un processus
linéaire obligatoire. On peut revenir sur les hypothèses et arbitrages à tout
moment. Aucun pourcentage, validation ou approbation n'est déduit de la lecture.
L'exercice est heuristique ; une validation auprès de lecteurs réels reste à faire.

## Réception prévue

Vérifier la présence des 38 sujets exactement une fois, leur hiérarchie,
les liens actifs des vues et diagrammes, les liens des pages d'entrée,
la navigation précédente/suivante, les parcours métier et réalisation,
les noms longs et le clavier. Vérifier 320, 390, 768 et 1440 pixels, avec
et sans JavaScript. Rejouer les trois dossiers Asteria et conserver les
résultats réellement exécutés dans la traçabilité.
