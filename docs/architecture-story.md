# Architecture story : expliquer un design exact

Chaque dossier du site AIR contient `story.html` et `story.json`. Le récit
reprend les sources autorisées de sa baseline : besoin et résultats attendus,
mécanismes, données, décisions et conséquences, évolution proposée, puis
préparation à la réalisation. Les cartes donnent le type ontologique, la
révision, les sélecteurs des propriétés et un lien vers l’objet complet.
Les textes longs sont signalés comme extraits, jamais réécrits en faits nouveaux.

La lecture libre conserve les six chapitres. Le mode court utilise quatre
moments en 24 secondes : Hook → Reveal → Highlights → Outro. Lecture, pause
et recherche avant/arrière sont disponibles, sans lecture automatique. Les
chapitres restent accessibles au clavier et sans JavaScript. La page et son
modèle sont inclus dans la conservation PWA explicite du site.

Une animation narrative n’est pas une exécution ni une simulation. Les chemins
de contrôle sont potentiels ; les gardes ne sont pas évaluées et les jointures
parallèles ne sont pas reconstituées. Les autres branches, limitations de
projection et lacunes restent dans le modèle et les pages de parcours. Les
comparaisons ne concernent que les paires de baselines explicitement choisies.
Les statuts de préparation calculés restent visibles, y compris NOT_READY.

## Vidéos BRAG et Hyperframes

Le skill portable [architecture-story](../src/air/skills/architecture-story/SKILL.md)
est livré avec AIR et exportable par `skills-export`. Il utilise le vrai
[BRAG](https://github.com/latent-spaces/brag) pour la narration courte, avec
Hyperframes pour la composition et le rendu. La recette locale est épinglée
au commit BRAG `cb89b9f44309b0bf4e3cb89e685fadf80c7999ed` et à Hyperframes
`0.8.114`. Le développeur peut les faire évoluer après une nouvelle qualification.

Python seul suffit à générer le site et le récit. Node, Chromium et FFmpeg
servent uniquement à l’atelier vidéo optionnel. Aucun CDN, compte cloud ou
service de voix n’est nécessaire à la lecture des livrables. La disponibilité
de ces outils dans ChatGPT/Claude cloud doit être vérifiée ; un skill n’accorde
pas à un client cloud l’accès au disque du poste.

```powershell
.venv/Scripts/python.exe -m air skills-export --target . --layout agents --skill architecture-story --apply
.venv/Scripts/python.exe scripts/prepare_architecture_trailers.py --help
```

Le script reçoit le site autorisé, un répertoire de sortie neuf, les assets
locaux licenciés et une capture réelle par dossier sélectionné. `--baseline`
prend un `id@revision` et peut être répété ; sans sélection, tous les dossiers
sont préparés. La numérotation D01/D02… suit leur ordre dans le manifeste.
La capture doit montrer une carte réelle de la baseline correspondante et
être vérifiée avant composition. `--fictional` désigne les démonstrations.

Il produit, par dossier, le plan BRAG, le brief, les sources, une composition,
les crédits et un reçu d’empreintes. Il refuse d’écraser un atelier existant.
La musique et les accents sont synthétisés localement par le script AIR, sous
Apache-2.0. La recette ne redistribue pas la musique embarquée de BRAG.
GSAP possède sa licence propre et Manrope sa licence OFL ; conserver les avis.
La voix est désactivée sauf demande explicite.

La réactivité audio optionnelle utilise `extract-audio-data.py` du skill
Hyperframes Creative sur la musique originale produite, à 30 fps, puis
`--audio-data`. L’analyse est une dépendance d’auteur, pas du runtime AIR.
Relire le texte, vérifier les poses et effectuer une recherche arrière/avant.

```powershell
npx --yes hyperframes@0.8.114 check <composition> --json --snapshots --at 0,3,8,15,22,24
npx --yes hyperframes@0.8.114 render <composition> --output <brag.mp4> --quality delivery --fps 30 --skill brag
```

Le rendu est une opération distincte de la préparation : un plan ne vaut pas
MP4 livré. Vérifier avec FFprobe la durée, la résolution, les pistes et les
frames. Choisir un poster lisible et le placer à la première frame selon BRAG.
Conserver le MP4, le poster et les empreintes ensemble.

Les MP4 sont des fichiers compagnons : le pack AIR borné à 16 MiB reste UTF-8.
Ils ne sont pas automatiquement copiés dans son cache PWA. Pour les transmettre,
conserver le répertoire de vidéos et le site complet ; aucune publication
externe n’est implicite. Le lecteur compagnon contient les liens du dossier.

`architecture_story.video_freshness(story, receipt)` compare baseline et
empreinte du récit : CURRENT signifie même source, STALE exige une nouvelle
lecture et un nouveau rendu. Ce contrôle ne valide pas la qualité d’une vidéo,
ses droits ni une solution métier. Le MP4 possède aussi une empreinte indépendante.

## Réception locale

Trois dossiers fictifs de la même entreprise Asteria sont les exemples :
portail SAV, maintenance connectée et mobilités/droits. Les deux états de chaque
design restent distincts. Les neuf cas d’exécution métier historiques restent
NOT_EXECUTED ; leur résultat n’est pas remplacé par une vidéo.

Le reçu de qualification (document historique ou livrable local non inclus)
documente les contrôles effectivement réalisés. La vidéo longue de deux minutes,
la présentation PowerPoint et la navigation 3D ne sont pas produites par cet
incrément. La lecture complète HTML couvre les six chapitres.
