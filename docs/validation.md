# Validation des sources publiques

La branche principale contient 0.35.0.dev1, version de développement. Les
résultats locaux de publication sont consignés dans
`traceability/public-development-035.json` avec leurs empreintes et limites.
La première suite publique a donné 1147 succès, 16 échecs et 2 skips.
Les échecs ont été traités : sources de fixture conservées, scripts optionnels
réintégrés, helper privé explicitement exclu et provenance des vues corrigée.
Le rejeu des cinq modules concernés donne 33 succès et 1 skip explicite.
La suite complète n’a pas été répétée après ces corrections.

Le wheel corrigé a passé installation neuve hors ligne, réinstallation et
restauration avec révocation de l’ancienne identité. Trois dossiers Asteria
et leurs 84 diagrammes ont été générés ; 12 vues News ont passé les contrôles
Chromium locaux à quatre largeurs. Aucune CI ni recette native n’est déduite.

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
