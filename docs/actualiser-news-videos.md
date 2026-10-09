# Actualiser les News et vidéos d’un projet

Le dossier raconte sa version actuelle et conserve ce qui reste à décider.
Chaque site AIR propose un encart **News du projet d’architecture** et une page
`news.html` : dernières informations déclarées, décisions et conséquences,
questions ouvertes, travaux actifs et contrôles de préparation encore ouverts.
Les sources exactes sont accessibles ; les dates auteur ne deviennent pas des
dates de livraison ou des approbations. Les extraits et éléments omis sont comptés.

## Avec l’assistant et le plugin

> Actualise les News, décisions et questions ouvertes de ce dossier. Puis
> actualise ses vidéos avec la même version, sans inventer de mesures ni d’avis.

L’assistant lit `air_query_project_updates`, régénère le site par
`air_compile_deliverables`, puis prépare les vidéos avec `air_refresh_videos`.
Ces outils sont exposés aussi au profil MCP guided ; le serveur contrôle les
droits sur la baseline avant génération. Ils sont disponibles dans le moteur
de développement courant, pas dans le moteur public rc9 inchangé.

Un MCP connecté à ChatGPT prépare les compositions ; il n’exécute pas un
renderer sur le serveur et ne publie pas de vidéo. Le rendu réel nécessite un
atelier autorisé avec Node, Chromium, Hyperframes et FFmpeg. Un agent local
peut l’utiliser ; un client cloud doit disposer d’un environnement de rendu.
Sans cela, le résultat reste explicitement `NOT_RENDERED`.

## Avec la CLI

Créer `actualisation.json` avec la référence exacte du dossier :

```json
{"baseline":{"id":"urn:exemple:baseline","revision":1,"digest":"sha256:REMPLACER_PAR_64_CHIFFRES_HEXADECIMAUX"}}
```

Depuis l’installation AIR (adapter les chemins ; Unix utilise `.venv/bin/python`) :

```text
.venv/Scripts/python.exe -m air --home <home> project-updates actualisation.json --credential <identite>.json
.venv/Scripts/python.exe -m air --home <home> deliverables demande-livrables.json --workspace <projet> --apply --credential <identite>.json
.venv/Scripts/python.exe -m air --home <home> videos-refresh actualisation.json --workspace <projet> --apply --credential <identite>.json
```

Pour produire les MP4 après préparation/relecture, ajouter `--render` à la
dernière commande. AIR utilise l’atelier Hyperframes 0.8.143 et FFmpeg, vérifie
la durée/résolution, le décodage et les empreintes, et conserve un reçu local.
Node/Chromium/FFmpeg restent facultatifs pour installer AIR ou lire le site.

La demande vidéo accepte `journey_id` pour choisir un parcours et `branding`
pour reprendre les paramètres de `branding/brand.json` (sa propriété `source`).
Sinon le premier parcours par identifiant et le branding AIR sont sélectionnés.
Les formats générés sont deux récits courts de 24 secondes : synthèse et
Customer Journey Map lorsque le dossier contient un parcours.

## Conserver les versions et leurs preuves

Les compositions sont générées dans `videos/<empreinte-source>/` : une évolution
de baseline, du branding ou des sources ouvre un autre atelier. Les fichiers
modifiés manuellement restent protégés par le plan de génération. Une vidéo
rendue et reçue est réutilisée si ses empreintes concordent ; une vidéo modifiée
n’est pas réétiquetée comme actuelle. Un MP4 interrompu sans reçu est préservé.

`source.json` conserve le récit, les News, le parcours choisi et leurs références.
La narration n’ajoute ni observation utilisateur ni réalisation du service.
Un index compagnon peut présenter les MP4 avec leurs posters et reçus ; ces
fichiers binaires ne font pas partie du cache PWA texte borné. Aucune publication
YouTube ou autre n’est déclenchée par l’actualisation.
