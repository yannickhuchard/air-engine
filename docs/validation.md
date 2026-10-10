# Validation des sources publiques

## Lot A reçu le 10 octobre 2026

La [consolidation locale](lot-a-consolidation.md) et son
[reçu](traceability/lot-a-2026-10-10.json) ajoutent la régression complète :
1 176 tests réussis, un skip explicite du helper privé, aucun échec. Les
retouches finales sont ensuite reçues par vingt tests ciblés publics.
Trois dossiers Asteria, 24 vues de la barre et la PWA sont rejoués.

Les builds produisent le même wheel et la même archive pour un commit donné.
Le paquet passe installation neuve hors ligne, réinstallation, mise à niveau
depuis rc9 et retour arrière par restauration. Les parcours natifs Codex et
ChatGPT sont observés, avec reprise du contexte et compilation des livrables.
Les configurations natives restent explicites ; la découverte automatique
Codex et l’annuaire OpenAI ne sont pas déduits de ces résultats.

La version reste 0.35.0.dev1, sans réception normative globale ni recette sur
un deuxième poste physique. Les autres clients/OS et PostgreSQL/OIDC ne sont
pas requalifiés par ce lot SQLite/local. Aucune CI lancée.

## Historique de la première publication

La branche principale contient 0.35.0.dev1, version de développement. Les
résultats locaux de publication sont consignés dans
`traceability/public-development-035.json` avec leurs empreintes et limites.
La première suite publique a donné 1147 succès, 16 échecs et 2 skips.
Les échecs ont été traités : sources de fixture conservées, scripts optionnels
réintégrés, helper privé explicitement exclu et provenance des vues corrigée.
Le rejeu des cinq modules concernés donne 33 succès et 1 skip explicite.
La suite complète n’avait pas encore été répétée à cette première publication.

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
Aucune CI push/PR n’est activée. Les autres OS, PostgreSQL/OIDC, les autres
clients natifs et la qualification globale de production restent à recevoir.
