# P06 - Exploitation sur le poste de l'architecte

Contrat de la candidate **0.34.0rc8**, schéma 6, profil `LOCAL_ARCHITECT_WORKSTATION`.
Le périmètre est Python/SQLite/identité locale sur un poste privé, API en boucle locale et adaptateurs
locaux. La réalisation des applications décrites dans les modèles ne fait pas partie de cette recette.

## Diagnostic utilisable par l'architecte ou son IDE

```sh
python -m air --home <home> workstation-check
```

Le diagnostic fonctionne serveur arrêté. Il vérifie les ACL/permissions du home et des secrets,
les fichiers réguliers sans liens de partage, l'identité locale, la configuration de boucle locale,
la base SQLite située dans le home privé, la validité du jeton, l'intégrité SQLite et la marge d'espace
libre. Il refuse un backend distant avant d'ouvrir une connexion ou de lire le jeton. Les valeurs de
configuration et les secrets ne sont jamais imprimés. Il ne corrige pas silencieusement les droits.

Retour 0 : `PASS` ; retour 2 : `FAILED`, avec contrôles booléens ; retour 1 : erreur de commande.
Le diagnostic ne prouve ni l'adresse effective d'un processus déjà lancé, ni la fraîcheur d'une
sauvegarde. Après démarrage, utiliser également `doctor` et `monitor`. Le profil local est une
qualification d'usage ; il ne supprime pas les autres modes de transport proposés par AIR.

Sous Windows, les ACL doivent n'accorder l'accès qu'au compte courant et à SYSTEM, sur un volume
avec ACL persistantes. Sous Unix, le home, la configuration et les identifiants doivent être privés
et appartenir au compte courant ; la traversée privée du home protège aussi les fichiers SQLite.
Le dernier périmètre effectivement mesuré et les OS reçus figurent dans la traçabilité.

## Sauvegarder et reprendre le travail

Le moteur propose une sauvegarde SQLite cohérente, sans Docker, IdP ni service central. Exemple :

```sh
python -m air --home <home> backup <nouvelle-sauvegarde>
python -m air --home <nouveau-home> restore <sauvegarde-verifiee>
python -m air --home <nouveau-home> workstation-check
```

1. Sauvegarder à la fin d'une session importante et avant une mise à niveau. Vérifier le code de retour
   et le manifeste ; un dossier `.pending-*` ne constitue pas une sauvegarde reçue.
2. Conserver une copie complète et protégée sur un support indépendant du poste selon la politique
   applicable. Ne pas copier une base SQLite active à la place de la commande de sauvegarde.
   La recette locale utilise un autre répertoire pour simuler un transfert : elle ne prouve pas la
   résistance d'un support physique indépendant.
3. Sur le poste de remplacement, réinstaller une version compatible, récupérer cette copie, puis
   restaurer dans un **nouveau home**. Aucun accès au home source n'est nécessaire.
4. Vérifier le diagnostic, les révisions/digests attendus, puis démarrer l'instance restaurée. Les
   anciens jetons sont révoqués ; reconnecter chaque adaptateur avec une nouvelle identité protégée.
   Réévaluer les mandats/revues selon la politique restaurée. Ne jamais réinjecter un ancien jeton.

Le point de reprise est **la dernière sauvegarde réussie**. Les dépôts ultérieurs ne réapparaissent
pas par magie ; la recette vérifie explicitement leur absence. AIR n'annonce ni ordonnanceur de
sauvegarde livré, ni RPO automatique, ni RTO incluant récupération du matériel et intervention humaine.
L'extra `backup` ajoute le chiffrement authentifié ; garder sa clé séparément, protégée et récupérable.
Il n'est pas requis pour le diagnostic ou la sauvegarde SQLite de base.

Les révisions et l'audit source sont conservés sans purge automatique. L'audit participe aux contrôles
d'auteur et de séparation des rôles. Conserver les sauvegardes connues comme restaurables avant de
retirer les copies plus anciennes ; définir leur durée selon les données du projet. AIR n'efface pas
automatiquement ces copies. Les règles imposant une purge du registre exigent une évolution reçue,
pas une suppression SQL improvisée. Support et traitement des vulnérabilités : [SECURITY.md](../SECURITY.md).
Les contacts, engagements et décision de mise en service sont reçus avec le pilote P08.

## Dossier local distinct du futur serveur

Le [modèle local](../examples/p06-workstation.template.json) utilise `air.p06-workstation/1` et
`profile=LOCAL_ARCHITECT_WORKSTATION`. Il référence quatre fichiers JSON avec chemin relatif et SHA-256 :
objectifs, charge, pannes/restauration et recette du poste. Le modèle historique `air.p06-reception/1`
reste celui du serveur ; un profil inconnu ou un profil local placé dans le format serveur est refusé.

```sh
python -m air operations-reception-check <dossier-local.json>
```

La commande recalcule les seuils, contrôle versions/environnements, empreintes, pannes, refus d'accès,
protection locale et reprise sans source. Elle n'exige ni PKI, ni IdP, ni collecteur d'alertes central.
Elle garde les limites de conservation et la perte possible depuis la dernière sauvegarde explicites.
Une pièce absente, altérée, un contrôle faux ou un seuil manqué ne peut pas être remplacé par un PASS
déclaratif. Les empreintes ne sont pas des signatures d'auteur.

`READY_FOR_INDEPENDENT_REVIEW` et `technical_checks_passed=true` signifient que les contrôles techniques
du dossier passent. `p06_received=false` et `production_ready=false` restent volontairement dans la
sortie : cette commande n'a pas autorité pour signer une réception produit ou le pilote d'une équipe.
La réception technique du lot dans le dépôt est consignée avec ses preuves et son périmètre ; le
pilote, la revue indépendante et la décision G1 restent P08, les clients natifs P07.

## Recette reproductible

Depuis un environnement de qualification équipé des dépendances de tests et de l'extra `backup` :

```sh
python scripts/qualify_workstation.py --work-root tmp/recette-poste --output tmp/reception-poste
python -m air operations-reception-check tmp/reception-poste/dossier.json
python scripts/demo_metier.py --output tmp/asteria-poste --qualify-external-proofs
```

Les tests synthétiques signés de la dernière commande demandent aussi l'extra `proofs`. Ce sont des
dépendances de recette ; l'installation de base n'impose aucun de ces extras. Chaque recette crée
ses propres homes privés et arrête ses serveurs. Elle refuse `AIR_DATABASE_URL` afin de ne pas utiliser
une base métier. Les sorties détaillées restent privées et ne doivent pas être committées.

La recette écrit les objectifs avant les mesures : quatre acteurs concurrents, trois dossiers Asteria,
69 révisions, 30 jobs pour dix cycles, pièces de 64 Kio ; p95 <=10 s pour les opérations HTTP et <=30 s
par calcul de job, pic RSS serveur <=512 Mio et enfant <=256 Mio, restauration mesurée <=30 s.
Les jobs sont soumis en concurrence puis traités séquentiellement. Augmenter les cycles ne crée pas
de nouveaux dossiers. Ce sont des seuils de référence testables, pas la capacité universelle d'un PC,
ni un engagement sur les quotas maximaux configurables du registre.

La protection locale est exercée par HTTP réel : accès anonyme/jeton invalide refusés, écriture refusée
au lecteur, diagnostic sans jeton. La restauration utilise une copie de sauvegarde après renommage du
home source, vérifie les digests, l'invalidation des anciens jetons, l'absence des changements postérieurs
et une nouvelle écriture sur l'instance restaurée. Le renommage ne concerne que le home jetable créé
par la recette ; aucune installation réelle n'est déplacée ou supprimée.

La matrice de panne exerce verrou SQLite, `SQLITE_FULL` par quota de pages et sortie brutale de processus.
Les tests de journalisation injectent ENOSPC ; ils ne remplissent pas le disque Windows physique.
Une panne électrique, la perte réelle d'un appareil, une synchronisation entre postes et le contrôle
cgroup Linux ne sont pas reçus par cette recette Windows. Les neuf scénarios ERP/atelier/IAM restent
non exécutés ; cela ne bloque pas la remise du design et des hypothèses aux équipes de réalisation.
