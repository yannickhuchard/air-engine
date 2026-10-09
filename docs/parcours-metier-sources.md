# Interroger les parcours métier déclarés

Incrément A02 du développement 0.35, le 2 octobre 2026. Le même service Python
sert la CLI, l’API HTTP, le MCP et les pages du site statique. SQLite et identité
locale restent les valeurs par défaut. Aucun système métier n’est appelé.

## Usage avec un agent

L’agent utilise `air_query_business_paths` sur des baselines exactes, autorisées.
La découverte est **lexicale** : tous les termes significatifs doivent figurer
dans le nom, la description ou les déclarations textuelles du modèle. Accents et
casse sont normalisés ; quelques mots de formulation sont ignorés. AIR n’effectue
ni traduction, ni rapprochement sémantique, ni recherche vectorielle. L’agent peut
reformuler les mots après lecture des candidats, sans annoncer un résultat absent.

~~~json
{
  "baselines": [{"id": "urn:entreprise:baseline:solution", "revision": 1, "digest": "sha256:REMPLACER_PAR_EMPREINTE_EXACTE"}],
  "query": "adresse correspondance"
}
~~~

L’empreinte doit être remplacée : cet exemple n’est pas exécutable tel quel.
La réponse contient `NOT_FOUND`, `AMBIGUOUS` ou un parcours sélectionné. En cas
d’ambiguïté, elle donne jusqu’à 64 candidats et le nombre total, sans choix
arbitraire. Pour sélectionner, remplacer `query` par :

~~~json
"start": {
  "baseline": {"id": "urn:entreprise:baseline:solution", "revision": 1, "digest": "sha256:REMPLACER_PAR_EMPREINTE_EXACTE"},
  "object": {"id": "urn:entreprise:workflow:adresse", "revision": 1}
}
~~~

Points d’entrée : Workflow, CustomerJourney, ValueStream, Capability,
BusinessService, Function, ArchitectureBlock. Le site prépare les trois premiers
types ; les autres restent disponibles via le service. Les catalogues guidés
et configurations générées pour Codex/Claude Code incluent le nouvel outil.
Un catalogue conservé par une installation existante doit être actualisé.
Ce changement ne qualifie pas une session native ChatGPT, Claude, Cursor ou
Antigravity, et ne modifie ni le plugin soumis ni la distribution publique rc9.

## Lire la réponse

- Workflows : entrées, étapes, participants, fonctions, branches, gardes, chemins
  potentiels, boucles, étapes inaccessibles, politique de fin et compensations.
- Contexte : acteurs, fonctions, opérations, contrats, blocs, ports, composants
  prévus, entités, schémas, événements et bindings de transport.
- Arêtes : référence, réalisation, binding d’opération, flux de données déclaré,
  avec objet exact, empreinte et sélecteur source.
- DataFlow : direction, schéma et finalité conservés. Connection : topologie
  déclarée, sans fabrication d’un appel métier.
- Messages : publication/abonnement, événement, canal et schéma conservés ; le
  partage d’un nom de canal ne prouve pas une route de transport.
- Modes d’échec et compensations : références conservées ; leur présence ne
  définit pas une branche, un déclencheur ou un ordre de reprise absent du modèle.

Les conditions ne sont pas évaluées. Même une garde formalisée `false` reste
visible dans les chemins potentiels. Un flux 0.32 sans garde est déclaré
inconditionnel ; une condition 0.22 en texte est signalée comme non formalisée.
Une jointure ALL produit un avertissement : la liste des branches ne reconstruit
pas la synchronisation ; utiliser la simulation de scénario pour cette autre tâche.

Les workflows retrouvés par une référence partagée sont identifiés comme
associés ; leur invocation par le point d’entrée n’est pas établie. Les scopes,
preuves et métadonnées de provenance ne servent pas de raccourcis de parcours.
`PARTIAL_DECLARATIONS` signale les lacunes détectées. `RESOLVED_DECLARATIONS`
signifie seulement que ces contrôles limités n’en ont détecté aucune : ni
complétude, ni causalité, ni conformité, ni autorisation d’exécution accordée.
La réponse conserve `causality_verified: false` et
`business_execution_performed: false`.

## Accès, limites et site

Toutes les baselines demandées sont autorisées avant la découverte des noms.
Un refus empêche la réponse partielle. Les révisions et dossiers ne fusionnent
jamais ; aucun parcours inter-dossier n’est fabriqué. Les octets des artefacts
de schéma ne sont pas téléchargés ; leurs droits restent ceux du service d’artefacts.

Budgets : 16 baselines, 16 000 objets en entrée, 32 768 arêtes par projection,
256 objets/6 niveaux/32 chemins/64 étapes par défaut ; maxima configurables
512 objets/12 niveaux/64 chemins/256 étapes. L’exploration des chemins est bornée
à 8 192 développements. Les limites atteintes sont signalées ; réponse bornée à
1 MiB. Le MCP conserve sa limite de 200 000 octets : réduire le contexte ou
utiliser la CLI si nécessaire.

~~~powershell
.venv/Scripts/python.exe -m air business-paths requete-parcours.json --credential architect.json
~~~

API : `POST /v1/business-paths/query`, identité authentifiée requise.
MCP stdio et HTTP : `air_query_business_paths`. Aucune écriture du registre.

Le site ajoute « Suivre les parcours métier », recherche locale et page de focus
par point d’entrée préparé : étapes, gardes, liens exacts, lacunes, JSON.
Limite : 64 points d’entrée préparés par dossier. Hors ligne, sans dépendance
Node pour l’installation, avec protection des modifications manuelles.

## Réception locale

Deux compléments **fictifs** aux trois dossiers Asteria décrivent l’adresse de
correspondance et une opportunité d’intervention au partenaire. Exigences,
données, contrats, blocs et flux sont explicitement déclarés ; les gardes restent
à formaliser. IAM expose volontairement ses liens de réalisation manquants.
Les neuf cas métier d’origine restent non exécutés.

~~~powershell
.venv/Scripts/python.exe scripts/demo_business_paths.py
~~~

Reçu de l’incrément (document historique ou livrable local non inclus).
Le graphe 2D filtrable, le temps, la 3D et AMASE discuté restent des étapes
distinctes de la [roadmap](roadmap-modeles-parcours-site.md).
