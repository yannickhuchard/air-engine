# ADR-45 - Reconstruction temporelle par connaissance du registre

Statut : adopté pour `air.bitemporal/1`, 28 septembre 2026.
Sources : white paper §5, annexe A.1 et règle AIR-V007 ; travaux L01.4/P10.

Une requête fixe deux instants UTC : `known_at`, heure de connaissance dans ce
registre, et `valid_at`, heure de validité déclarée. Le champ `stored_at`, attribué
par le registre à la première insertion, détermine la connaissance. Le champ
`meta.recorded_at`, fourni par l'auteur, ne peut antidater cette connaissance.

Pour chaque identifiant demandé, AIR sélectionne la plus grande révision parmi
celles reçues au plus tard à `known_at` dont l'intervalle déclaré contient
`valid_at`. Les intervalles sont fermés à gauche et ouverts à droite. Une fin
nulle est illimitée. Des révisions peuvent arriver dans un ordre différent de
leur numérotation ; le numéro exprime la succession, l'arrivée exprime la connaissance.

La sélection est déterministe et ne crée aucune baseline. Ses références peuvent
pointer vers d'autres instants : la fermeture et la cohérence de l'ensemble restent
à vérifier explicitement. L'autorisation est celle de la lecture actuelle, y
compris pour les références transitives ; une date ancienne ne restaure pas des droits.
Une requête dépassant 4 096 révisions est refusée sans sélection partielle.

Ce contrat conserve les anciens octets, schémas, profils et digests. Il ne change
pas les statuts éditoriaux et ne reçoit pas à lui seul tout le lot P10. La sauvegarde
du registre conserve les heures de réception ; un nouvel import de simples objets
est une nouvelle connaissance locale et ne prétend pas reconstruire un registre distant.
