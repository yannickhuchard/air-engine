# Comparer les états et les dates d’un projet

Le développement **0.35.0.dev1** ajoute `site/timeline.html` et `timeline.json`
aux packs complets. La page est accessible depuis le projet et chaque dossier,
hors ligne et sans serveur. Elle distingue trois lectures : les changements
entre deux designs choisis, la validité déclarée des objets et le calendrier
prévu de transformation.

## Choisir les états à comparer

Une comparaison doit être déclarée dans la requête `deliverables`. Ses deux
extrémités doivent figurer dans `baselines` avec le même identifiant, la même
révision et la même empreinte exacte. Exemple de structure, avec empreintes
à remplacer par celles retournées par AIR :

```json
{
  "title": "Transformation du service partenaires",
  "baselines": [
    {"id": "urn:entreprise:baseline:partenaires", "revision": 1, "digest": "sha256:<empreinte A>"},
    {"id": "urn:entreprise:baseline:partenaires", "revision": 2, "digest": "sha256:<empreinte B>"}
  ],
  "comparisons": [
    {
      "title": "Design de référence / cible proposée",
      "before": {"id": "urn:entreprise:baseline:partenaires", "revision": 1, "digest": "sha256:<empreinte A>"},
      "after": {"id": "urn:entreprise:baseline:partenaires", "revision": 2, "digest": "sha256:<empreinte B>"}
    }
  ]
}
```

Les placeholders de cet exemple ne sont pas des références exécutables.
La CLI, HTTP et MCP utilisent la même compilation de livrables. La page
temporelle est générée même sans paire, mais elle dit alors qu’aucune
comparaison n’a été choisie. Les noms « existant » ou « cible » ne sont pas
déduits des noms de fichiers ou des dates ; l’architecte choisit le sens de
ses états. Deux namespaces différents sont signalés comme périmètres différents.

Le moteur `air.temporal-site/1` compare par identité d’objet, en conservant ses
révisions et empreintes de chaque côté. Les statuts distinguent ajout, retrait,
contenu, métadonnées, seules références révisées, seule révision/date auteur et
objet identique. Une ligne mène aux définitions exactes et à tous ses champs
différents, calculés avec le même comparateur de champs que les projections AIR.
La compatibilité sémantique et la migration restent `NOT_EXECUTED`.

Le registre impose une seule révision par identité dans une baseline fermée
(`AIR_BASELINE_VERSION_AMBIGUOUS`). La projection défensive regroupe des révisions
multiples sans choisir de paire arbitraire si elle reçoit directement un export
non standard ; cela ne permet pas de l’enregistrer comme baseline valide.
Les définitions des révisions choisies restent accessibles dans leur propre état.
Les graphes 2D des états A et B restent
séparés, avec liens directs depuis la comparaison.

## Naviguer dans la validité et le calendrier

Choisir un état puis une frontière de validité, par liste ou curseur, affiche
les objets dont l’intervalle déclaré contient cet instant. Le début est inclus,
la fin exclue. Les frontières sont normalisées en UTC avec microsecondes ; les
offsets et précisions sont conservés dans la déclaration source. Une fin absente
reste non déclarée. L’échelle du dessin est indicative ; elle ne décide pas
l’inclusion à une frontière.

Le curseur parcourt les dates de début/fin présentes dans le snapshot ; il ne
fait pas une reconstruction historique du registre. Il peut masquer un objet
référencé par un autre : la vue filtrée **n’est pas une nouvelle baseline fermée**.
Le JSON et les définitions exactes gardent les objets du snapshot original.

Les Milestone affichent leurs dates et critères de sortie prévus ; les phases
Roadmap affichent leurs intervalles et critères déclarés. Une date calendaire
invalide ou un intervalle inversé est signalé et n’est pas dessiné comme une
date corrigée. Aucun état réalisé, déployé, migré ou arrêté n’en est inféré.

La date `recorded_at` vient de l’auteur. L’export statique ne contient pas la
date de réception réelle `stored_at` et ne s’en sert donc pas pour reconstruire
ce qui était connu. Le service séparé `air_reconstruct_temporal` conserve sa
sémantique bitemporelle et ses droits actuels ; il ne devient pas automatiquement
une baseline fermée ou une acceptation du design.

## Portée et réception

Les endpoints sont limités aux snapshots autorisés avant compilation : aucun
historique caché n’est découvert, et une paire absente ou avec mauvaise empreinte
refuse la génération. Les comparaisons nécessitent le site complet ; `only` ou
`website: false` avec une paire explicite est refusé.

Bornes : 16 baselines, 16 paires, 1 000 objets par snapshot, 4 MiB par ressource
du site et 16 MiB par pack. La projection conserve tous les objets admis ; un
dépassement refuse la compilation. La lecture affiche au plus 150 lignes par
dessin/liste, avec compteur et JSON complet. Sans JavaScript, les états, dates,
résumés de comparaison et liens de sources restent accessibles.

La recette présente trois solutions fictives Asteria, chacune avec deux états :
le champ lié devient obligatoire, son schéma et sa colonne physique changent,
les références sont propagées et une revue de migration est planifiée. Les
plans de migration/retour arrière restent à produire ; aucune migration réelle
n’est jouée. Les neuf cas métier originaux restent NOT_EXECUTED et les portes
NOT_READY. Commande locale :

```powershell
.venv/Scripts/python.exe scripts/demo_temporal_site.py --output tmp/temporal-site-20261003
```

Lire le reçu de réception (document historique ou livrable local non inclus).
Cette lecture des états et dates ne reçoit pas un moteur général de graphes 4D,
une trace de simulation animée, la 3D, une fusion inter-dossiers ou le profil
AMASE. La distribution publique rc9 et les clients natifs restent distincts.
