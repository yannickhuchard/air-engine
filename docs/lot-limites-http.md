# P06 - Concurrence par identité et réception des documents

Candidate 0.34.0rc5, schéma 6 inchangé. P06 reste IN_PROGRESS : ces limites techniques
ne reçoivent ni la capacité du groupe, ni ses objectifs de service.

Réception du commit **5531927** : 12 tâches CI réussies et rapports (document historique ou livrable local non inclus),
recettes HTTP réelles sur Windows/Linux, trois dossiers Asteria rejoués et non-régression des sauvegardes
et de la reprise. Les objectifs d'entreprise et les budgets complémentaires restent ouverts.

## Configuration

Les variables sont lues au démarrage du serveur. Redémarrer le processus identifié après changement.
Une valeur invalide empêche son démarrage ; aucune nouvelle dépendance n'est nécessaire.

| Variable | Défaut | Valeurs | Effet |
| --- | --- | --- | --- |
| `AIR_MAX_INFLIGHT` | 32 | Entier 1..1024 | Limite globale HTTP déjà livrée ; excès : 503 `AIR_BUSY` |
| `AIR_MAX_INFLIGHT_PER_SUBJECT` | 8 | Entier 1..1024 | Requêtes authentifiées simultanées d'un même sujet ; excès : 429 `AIR_SUBJECT_BUSY` |
| `AIR_BODY_TIMEOUT_SECONDS` | 30 | Nombre fini 1..300 | Durée totale de réception d'un document JSON ; dépassement : 408 `AIR_INPUT_TIMEOUT` |

Les réponses 429/503 portent `Retry-After: 1`. Attendre avec un nombre de tentatives borné,
puis signaler l'échec si la saturation persiste. Ne rejouer une mutation qu'en respectant
son contrat d'idempotence ; ne pas renouveler un jeton pour contourner la limite.

## Portée et libération

Le quota par sujet commence après authentification et chargement de la politique. Plusieurs
jetons du même sujet partagent le même compteur ; API et MCP HTTP partagent aussi ce compteur.
Une connexion partagée conserve donc une limite commune à son identité de service. Une autre
identité peut continuer tant qu'il reste de la capacité globale. Les sondes `/health` et `/ready`
restent exemptées. Les métriques administrateur sont, elles, soumises aux deux limites.

La place est libérée à la fin de la dépendance d'identité, après émission normale de la réponse,
y compris en cas d'erreur ou d'annulation. Le compteur du sujet disparaît à zéro. Il n'y a pas de
file d'attente supplémentaire, de quota persistant ni de partage entre processus. Le serveur
livré utilise un processus ; CLI, MCP stdio et jobs en arrière-plan ne sont pas limités par ce contrôle.

Le délai de réception commence à l'entrée du lecteur de document, après authentification et contrôle
du type JSON. Il couvre toute la réception, sans remise à zéro à chaque fragment. Le plafond existant
de 1 048 576 octets est contrôlé avant copie du fragment dans le tampon. Un Content-Length trop grand
est refusé avant lecture (413) ; absent, la limite reste appliquée au flux. Une longueur déclarée invalide,
multiple ou différente du contenu reçu est refusée (400). Une déconnexion ne devient pas un document partiel.
Le parseur et les opérations métier ne sont appelés qu'après réception complète.

Ce délai coopératif ne borne ni l'authentification, ni le calcul métier, ni l'émission d'une réponse.
Il ne tue pas un thread Python en cours de calcul. Un proxy d'entreprise doit encore traiter les
connexions, les en-têtes lents, les limites réseau et ses propres délais. Le tampon du serveur ASGI
peut déjà contenir le fragment reçu ; ce contrôle ne garantit pas une consommation mémoire totale
égale à la taille du document. Les budgets CPU/mémoire, jobs, stockage et quotas par namespace restent ouverts.

## Observation et recette

`GET /v1/operations` ajoute `identity_admission` (plafond, nombre de sujets actifs et refus)
et `input_limits` (taille, délai et compteurs de refus par code fixe). Aucun sujet, jeton, chemin,
contenu ou label libre n'est exposé. Ces compteurs repartent de zéro au redémarrage.

```text
python scripts/qualify_http_limits.py --work-root <volume-prive> --output <nouveau-rapport.json>
```

La recette refuse `AIR_DATABASE_URL`, crée une installation SQLite jetable et ne reçoit aucun home métier.
Elle utilise un vrai serveur et une connexion TCP incomplète : deuxième jeton de même identité limité,
autre identité disponible, sonde disponible, expiration à cinq secondes configurées, taille déclarée
excessive refusée, zéro révision partielle, dépôt ultérieur réussi et compteurs administrateur vérifiés.
Le serveur identifié est arrêté ; seuls résultats fixes, configuration et temps observé entrent dans
le rapport public. La CI rejoue cette recette sur Windows/Linux et les trois dossiers Asteria séparément.

`tests/test_http_budgets.py` couvre également le flux lent par petits fragments, MCP HTTP, l'annulation,
les longueurs invalides, la déconnexion et la confidentialité des métriques. La charge synthétique
de `qualify_operations.py` utilise une seule identité : pour augmenter sa concurrence au-delà de huit,
configurer aussi le plafond par sujet ; un rejet fait échouer cette recette, il n'est pas masqué.

Références : [annulation et délais asyncio](https://docs.python.org/3/library/asyncio-task.html#timeouts),
[durée de vie des dépendances FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).
