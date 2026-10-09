# Catalogue des parcours, personas et usages

Chaque dossier AIR généré expose `journeys.html` et `journeys.json`, une page
de focus par parcours, un accès dans la navigation et un aperçu sur l’accueil.
Le sujet 03 fournit le catalogue et les usages en Markdown. Le sujet 34, la
checklist de l’accueil et le kanban portent les mêmes cinq contrôles calculés.
Les anciens dossiers restent lisibles ; leurs manques sont affichés.
Les [cartes d’expérience et processus en couloirs](diagrammes-processus-et-experience.md)
ajoutent phases, pensées, émotions sourcées, systèmes et service blueprint.
Les cases absentes restent visibles, sans modifier les cinq contrôles existants.

## Ontologie et contributions CLI/MCP

Décrire les schémas courants avant contribution. `JourneyCatalog` déclare un
périmètre Scope, la liste des CustomerJourney et un roster de personas
Actor/Stakeholder. Chaque persona est requis ou exclu avec justification et
contextes requis. Inclure clients et autres intervenants pertinents : support,
opérations, gouvernance, partenaires et public. La liste porte une exhaustivité
documentaire dans son périmètre déclaré, sans prétendre couvrir tous les usages
possibles ou remplacer les entretiens.

Une étape de CustomerJourney conserve son ordre, canal et texte de contact.
Elle peut déclarer `touchpoint_ref`, `participants`, `architecture_links` et
`outcome`. Touchpoint décrit purpose, usage_points, participants,
architecture_links et accessibility. UsagePoint distingue DIGITAL, PHYSICAL
et GEOGRAPHIC, avec statut proposé ou confirmé selon déclaration, finalité,
lieu descriptif et parent éventuel. Le lieu exact n’est pas obligatoire : un
dépôt ou corridor à sélectionner doit rester visible. Aucune géolocalisation
d’une personne n’est nécessaire pour documenter le design.

Les liens sont des références exactes aux fonctions, contrats, blocs, données,
exigences, contrôles, coûts ou livrables existants. Leur provenance est attachée
à l’objet et au sélecteur du champ. Les slots sont résolus par le même noyau,
alimentent le graphe du site et les requêtes `air_query_business_paths` depuis
le parcours. La proximité dans le graphe ne devient pas un appel causal.

Modifier avec le workflow de drafts existant, valider puis rebaser, examiner
le candidat, déposer et figer dans la portée autorisée. CLI et MCP utilisent
les mêmes schémas et services. Compiler le site depuis la nouvelle baseline
exacte, pas depuis des fichiers modifiés sans révision dans le registre.

## Checklist et limites

Les cinq contrôles vérifient : périmètre et personas inventoriés ; un parcours
pour chaque persona requis et rattachement de tous les parcours ; contacts
typés à chaque étape ; contextes requis déclarés et absence de cycle de lieux ;
liens d’architecture par étape et références résolues. Les intervenants externes
explicitement liés doivent aussi être inventoriés. Un persona dans plusieurs
catalogues est signalé, pour éviter une fusion ou une exclusion ambiguë.

Ces contrôles sont documentaires. Ils ne démontrent pas la qualité d’un
entretien, une accessibilité effectivement reçue, une conformité réglementaire,
une autorisation de corridor ou une exécution en production. Ils restent
distincts des douze critères de préparation `readiness` et ne modifient pas
leur score. Le JSON conserve sources, lacunes, baseline et empreinte.

## Choix de lecture

L’entrée par persona répond à « qui veut accomplir quoi ? ». Les cartes
séparent service nominal, exception, assistance, exploitation et gouvernance.
Une page de focus raconte chaque parcours : intention, déclencheur, résultat,
étapes, intervenants, usages, lieux, irritants et preuves des liens. Les listes
restent intégrales sans JavaScript ; le filtre est un confort de lecture.
L’interface réutilise le branding, le responsive et le cache PWA du dossier.
Ce choix est une hypothèse de conception UX, pas une séance de recherche
utilisateur déjà réalisée.

## ProxiBot

Le catalogue proposé couvre 21 parcours, 48 étapes et 17 personas requis.
Le robot est un acteur technique explicitement exclu des personas humains.
Les 48 contacts relient 14 points d’usage et quatre territoires géographiques :
Differdange, Esch-sur-Alzette, Arlon et Metz. Les villes sont celles du cadrage
utilisateur ; dépôts, commerces, corridors et points de remise sont à choisir.
Un seul pilote local est envisagé à la fois, sans trajet transfrontalier ou
interurbain. Recherche utilisateur, OEM, assurance, autorisations et sites
réceptionnés ne sont pas inventés.

La compilation complète d’un grand site peut être longue : le MCP accepte
le même délai borné de 600 secondes que la CLI. Demander DIGESTS côté agent ;
les limites de taille des réponses et l’authentification sont conservées.
