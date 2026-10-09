---
name: architecture-story
description: Expliquer un dossier AIR par un récit sourcé, un lecteur HTML et des vidéos courtes BRAG/Hyperframes. Utiliser pour raconter les besoins, mécanismes, données, décisions, évolution prévue et prochaines vérifications d’une baseline exacte, sans assimiler narration et exécution métier.
---

# Architecture story AIR

Lire README.md, docs/etat-implementation.md et docs/architecture-story.md du
dépôt AIR. Respecter les droits du projet et ses instructions AGENTS.md.

## Source unique

1. Choisir une baseline autorisée, avec id, révision et empreinte. Plusieurs
   états restent plusieurs dossiers. Aucune fusion implicite.
2. Générer le pack complet avec `air_compile_deliverables`, ou la commande
   `deliverables` documentée dans le dépôt. Appliquer le plan de fichiers avec
   protection des modifications manuelles. Ne pas récupérer un jeton en texte.
3. Lire `site/site-manifest.json`, puis le `story_data` du dossier choisi.
   `story.json` porte l’empreinte du récit, les objets exacts et les sélecteurs
   des propriétés. Vérifier avec `air.architecture_story.verify`.
4. Expliquer les six chapitres : besoin, mécanismes, données, choix,
   évolution, préparation. Les limites, objets omis et chapitres vides sont
   explicites. Ouvrir les sources complètes pour les branches et propriétés.

Le site statique fonctionne avec Python seul et reste lisible sans JavaScript.
Le lecteur court est une présentation de 24 secondes, pas une trace de
simulation. Les dates sont la validité et le calendrier déclarés ; aucune
migration, interaction causale ou exécution n’est inférée.

## Vidéos en option

Pour une demande de vidéo, utiliser le vrai skill BRAG :
https://github.com/latent-spaces/brag/tree/cb89b9f44309b0bf4e3cb89e685fadf80c7999ed/skills/brag

Lire son SKILL.md puis ses références inspect/plan/compose/deliver. Lire les
domaines Hyperframes actuels (core, animation, creative, keyframes, CLI).
Ces outils sont optionnels : Node, navigateur Chromium et FFmpeg ne deviennent
jamais des dépendances d’installation AIR. Leur disponibilité dépend du poste
ou du bac à sable de l’agent ; un client cloud doit pouvoir accéder aux sources
autorisées et disposer d’un environnement de rendu pour produire un MP4.

Préparer un répertoire compagnon neuf, hors du pack UTF-8 borné. Le script
`scripts/prepare_architecture_trailers.py` du dépôt prépare les plans, briefs
et compositions à partir du même `story.json` (voir sa commande `--help`).
Les quatre scènes suivent les chapitres purpose/mechanism/choices/next, avec
des temps 0/5/12/19/24. Les données et l’évolution restent dans le récit long.
Afficher au moins un élément réel du site ou de ses sources. Ne pas reprendre
des composants d’un exemple externe dans l’architecture du projet.

Musique et effets doivent avoir une provenance/licence vérifiée. Pas de voix
sans demande. Pas de publication externe sans autorisation. Garder les MP4,
poster, plan, brief, composition, crédits et reçu d’empreintes ensemble.

Contrôler la lisibilité aux poses clés et les recherches arrière/avant. Exécuter
`hyperframes check` avant rendu. Rendre localement lorsque la demande l’autorise,
puis vérifier durée, résolution, pistes, poster et empreintes des sources.
`air.architecture_story.video_freshness(story, receipt)` distingue CURRENT et
STALE ; CURRENT signifie uniquement même source, jamais une validation métier.
Toute nouvelle révision exige une nouvelle lecture et un nouveau rendu.

## Livraison

Présenter le lecteur HTML et les MP4 réellement rendus. Indiquer la baseline,
les sources, les limites et les contrôles effectués. Un storyboard seul n’est
pas une vidéo livrée. Ne pas rendre une porte NOT_READY verte par la narration.

Pour raconter les expériences, lire aussi `journeys.json` et les pages par
parcours : partir du persona, du besoin et du lieu, puis montrer les points de
contact et leurs liens exacts au dossier. Préserver les exceptions, l’assistance
humaine, les exclusions et les lieux proposés. Une narration ne valide pas
les usages par des utilisateurs réels.

## Actualiser News et vidéos

Pour une demande de mise à jour, lire `air_query_project_updates` sur la baseline exacte.
Les News sont des déclarations sourcées, pas une preuve de livraison ou d’approbation.
Régénérer le site par `air_compile_deliverables` ; préserver les questions ouvertes.
Si le catalogue expose `air_refresh_videos`, commencer par DIGESTS, puis obtenir
les fichiers FULL pour l’atelier autorisé. Le MCP prépare sans écrire ni rendre
sur le serveur. La CLI `videos-refresh --apply --render` rend localement avec
Hyperframes/Chromium/FFmpeg facultatifs. Sans cet atelier, annoncer NOT_RENDERED.
Une ancienne vidéo n’est pas courante par simple changement de son étiquette :
contrôler la baseline, le source_digest, le branding et le reçu du rendu réel.
Aucune publication externe implicite. Les fonctions nécessitent le moteur courant
qui les expose ; ne pas les supposer disponibles dans la distribution rc9.
