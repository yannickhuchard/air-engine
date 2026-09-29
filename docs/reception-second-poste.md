# Recette publique sur un second poste

Ce kit reçoit la distribution publique **0.34.0rc9**, avec Python 3.11+,
SQLite et identité locale. Il ne qualifie ni 0.35, ni le serveur centralisé, ni
l’annuaire ChatGPT. Windows/Python 3.12 reste la plateforme de référence ; un essai
sur un autre OS doit être identifié comme tel. Aucun Docker, Node ou Git obligatoire.

## Exécuter

Télécharger le kit `air-rc9-reception-kit-20260930.zip` depuis les assets de la
[release officielle](https://github.com/yannickhuchard/air-engine/releases/tag/v0.34.0rc9),
vérifier son SHA-256 avec le reçu du kit publié à côté, puis extraire dans un dossier neuf.
Le kit contient les deux scripts de recette, pas un nouveau moteur.
On peut aussi utiliser ces scripts depuis le dépôt public courant.

Depuis ce dossier, dans un terminal sans variables AIR ni PYTHONPATH personnalisées :

```text
python scripts/receive_public.py --output reception-001
```

Choisir un autre nom si la destination existe. Ne jamais donner un home AIR métier.
Ne pas lancer Python avec `-O`. Utiliser un disque local privé avec ACL persistantes
sur Windows. Internet est nécessaire pour GitHub et le registre pip (ou un miroir
configuré). Les étapes d’installation utilisent ensuite le wheelhouse téléchargé
sans accès à l’index : cela ne signifie pas que tout le kit est exécutable sans réseau.

Le script vérifie les quatre artefacts rc9 par SHA-256 épinglé, crée une nouvelle
venv, reçoit installation/réinstallation/sauvegarde/restauration, puis rejoue les
trois dossiers Asteria par HTTP et MCP. Les serveurs de recette sont arrêtés à la fin.
Il ne remplace pas une installation existante et ne connecte pas automatiquement un IDE.
Un échec retourne un code non nul et ne produit pas de reçu PASS.

## Lire le résultat

`reception-001/receipt.json` est le résumé sans chemins ni identifiants privés.
Il doit conserver les résultats calculés : D01 UNKNOWN, D02 VIOLATED, D03 CONFLICTING,
trois portes BLOCKED et neuf tests métier NOT_EXECUTED. PASS_SCOPED reçoit le parcours
de conception, pas la réalisation des solutions décrites.

Les trois vues `D01.html`, `D02.html`, `D03.html` se trouvent dans le sous-dossier
`private/air-release-…/asteria`. Les rapports complets, bases et identités y sont privés.
Ne partager ni tout le dossier de recette, ni ses logs, ni les credentials.
Certains rendus utilisent des ressources web ; ne pas promettre des vues entièrement hors ligne.

## Réception humaine distincte

Le script laisse `second_physical_device=NOT_ATTESTED` et crée `owner-review.json`.
Sur une machine réellement différente de celle du développeur, l’opérateur renseigne
son alias, un alias de poste non identifiant, l’IDE et sa version, l’installation sans
assistance du développeur, la lecture des trois vues et ses observations. Il peut
remplacer son statut par ACCEPTED ou REJECTED seulement après ces vérifications ;
ne pas modifier le reçu calculé, auquel l’attestation se lie par SHA-256.

Pour la recette de l’agent natif, suivre [la connexion des agents](agents.md) dans
un registre fictif explicitement autorisé. Vérifier sa vraie connexion, ses droits,
une lecture de baseline exacte et le refus de fabriquer un PASS quand il manque
des données. Une recette HTTP/MCP par script ne vaut pas cette recette utilisateur.

Ne partager que `receipt.json` et `owner-review.json` après relecture. Pour arrêter
une recette interrompue, l’IDE doit utiliser `scripts/install.py --stop` avec le home
et la venv exacts de l’instance identifiée ; ne jamais tuer des processus par nom.
Le kit n’efface pas les preuves ni les environnements après exécution.

## Prompt à donner à l’IDE du second poste

> Lis README.md et docs/reception-second-poste.md. Installe les prérequis manquants
> seulement selon les règles de mon poste, puis exécute la recette dans un dossier
> neuf. Montre-moi les trois vues Asteria et leurs résultats calculés. Ne lis pas
> les secrets dans le chat. Laisse les tests non exécutés visibles et ne prétends
> pas qu’une simulation exécute le système métier. Prépare owner-review.json pour
> ma revue, sans inventer l’identité du poste ni mon acceptation.
