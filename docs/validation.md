# Validation des sources publiques

La branche principale contient 0.35.0.dev1, version de développement. Les
résultats locaux de publication sont consignés dans
`traceability/public-development-035.json` avec leurs empreintes et limites.
Les vérifications seront enregistrées après leur exécution, sans résultat prévu
transformé en preuve.

La release [0.34.0rc9](https://github.com/yannickhuchard/air-engine/releases/tag/v0.34.0rc9)
et ses archives restent inchangées. Ses preuves s’appliquent uniquement à cette
distribution, pas aux nouveautés 0.35. Le kit de
[réception second poste](reception-second-poste.md) vise rc9.

La publication 0.35 ne comprend pas le PDF original du white paper, les dossiers
privés ou les journaux de sessions. Les tests de l’inventaire lié à ce PDF et du
budget et de la consultation privés ProxiBot sont exclus de la sélection publique ; les contrôles du
moteur et les exemples Asteria sont inclus. Le test des baselines historiques
utilise la même fixture publique déjà distribuée avec rc9. Le seul test de
conservation des simulations historiques qui dépend du helper privé de recette
ProxiBot est explicitement ignoré lorsque ce helper n’est pas distribué.

Pour contribuer : `python scripts/install.py --extras dev,proofs,backup`, puis
`.venv/Scripts/python.exe scripts/check.py -q` sous Windows
(`.venv/bin/python` sous Unix). Le dossier temporaire doit être local et privé.
Aucune CI push/PR n’est activée. Les autres OS, PostgreSQL/OIDC, les nouveaux
clients natifs et la qualification globale de production restent à recevoir.
