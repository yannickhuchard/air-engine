# Modèles fidèles, parcours métier et sites d’architecture

Décision du 2 octobre 2026, après analyse de la checklist AMASE : enregistrer le
mapping, avancer sur les exports et ajouter un site HTML statique pour chaque
projet, réunissant ses dossiers de solution. Un sujet de focus correspond à une
page ; chaque diagramme possède aussi une page dédiée.

Cette roadmap complète P10–P14 ; elle ne les clôture pas. Le développement reste
distinct de la distribution publique rc9 et de sa qualification. Python/SQLite,
identité locale et fonctionnement décentralisé sont conservés. Aucune CI.

## A01 - Export fidèle des modèles déclarés

Priorité immédiate. Conserver sans perte les objets de chaque baseline, leurs
révisions, empreintes et schémas de types. Inclure les octets autorisés des
artefacts DataSchema, sans résolution réseau ni collecte de sources externes.
Corriger la restitution des identités, cardinalités déclarées et nullabilité.
Ne pas inventer les multiplicités inverses ou confondre ontologie et stockage.

Réception : comparaison objet par objet avec le registre ; empreintes des
artefacts identiques ; changement de nullabilité/cardinalité visible ; références
à deux révisions distinctes conservées ; erreurs d’accès sans export partiel.

Limites : export complet de ce qui est déclaré, pas complétude du design. Les
contraintes d’entité, migrations, UNIQUE/CHECK et DDL par moteur nécessitent un
binding ultérieur. RDF/JSON-LD n’est pas une dépendance de ce lot.

## A02 - Parcours métier sourcés

Ajouter un service commun CLI/API/MCP pour résoudre une intention vers les
parcours déclarés : acteurs, workflows, fonctions, contrats, composants, données,
canaux et consommateurs. Distinguer liens de référence, flux, contrôle de
processus et causalité explicitement modélisée. Conserver les gardes, branches,
erreurs, compensations, références exactes et ruptures de traçabilité.

Réception : parcours d’adresse de correspondance et proposition proactive
d’opportunité partenaire ; ambiguïtés et parcours incomplets explicités ; même
résultat moteur depuis chaque adaptateur ; aucun appel métier réel. Les clients
non qualifiés restent documentés comme tels, notamment Cursor/Antigravity.

Incrément livré : [requêtes de parcours sourcés](parcours-metier-sources.md),
découverte lexicale et sélection exacte, chemins potentiels et contexte typé,
lacunes, parité HTTP/MCP, pages de focus dans le site. Les baselines restent
séparées ; les liens de référence ne deviennent pas causalité métier. Le
rapprochement sémantique des intentions, les appels inter-workflows et une route
causale entre dossiers restent hors de cette portée.

## A03 - Profil de revue AMASE

Le [mapping des 48 contrôles](mapping-amase.md) est une proposition de discussion,
pas un profil intégré ou une certification. Après revue : contrôles versionnés,
applicabilité, responsable, preuve exacte, résultat et action de fermeture.
Adapter les obligations au contexte ; non-applicabilité motivée ; ne jamais
déduire la satisfaction d’un contrôle de la présence d’un document ou d’un type.

Réception : contrôle absent, déclaration sans preuve, preuve insuffisante,
contradiction, exception motivée et contrôle effectivement calculable. Conserver
séparément complétude documentaire, vérification du design et approbation humaine.
Discuter migrations/coexistence/retour arrière, qualité et cycle de vie des
données, performance, accessibilité et fin de vie avant extension du profil.

## A04 - Site statique de chaque projet

Le premier incrément est livré avec A01 : génération par `deliverables`, sans
hébergeur, CDN, Node ou service IA obligatoire. Accueil du projet, dossiers
épinglés distincts, parcours de lecture, 37 pages de focus par dossier, pages de
diagrammes, définitions des objets et liens vers les révisions exactes. Descriptions
déterministes des besoins, mécanismes, choix et conséquences ; les informations
absentes ne deviennent pas un récit inventé.

Réception : tous les sujets/diagrammes du catalogue présents, liens et ancres
valides, rendu hors ligne, recherche, clavier, écran étroit, zoom, texte hostile
inerté, absence de secret et aucune modification du registre. Régénération avec
protection des modifications manuelles. Démonstration des trois dossiers Asteria.

Incrément du 3 octobre : [graphe 2D filtrable par dossier](graphe-architecture-2d.md),
couches ontologiques, types et relations, voisins directs, panneau de sources,
surbrillance du contexte des parcours A02, zoom et miniature. Les références
restent distinctes des interactions ; les baselines ne sont pas fusionnées.

Incrément suivant du 3 octobre : [comparaisons d’états exacts et dates](comparaison-temporelle-site.md),
avec paires explicites, changements sourcés, curseur de validité et calendrier
Milestone/Roadmap prévu. Les états ne sont pas reconstruits ni fusionnés par le curseur.

Suite de A04 : navigation du graphe par le temps et traces de simulation sourcées.
Distinguer temps de connaissance, validité du design, calendrier de transformation et trace simulée. La sélection
bitemporelle 0.35 n’est pas une baseline fermée. La 3D reste optionnelle et doit
améliorer la compréhension sur des tâches mesurées avant réception.

## État de cet incrément

| Périmètre | Statut |
| --- | --- |
| A01, export exact des informations actuellement déclarées | Implémenté ; réception locale dans le reçu associé |
| A01, contraintes étendues et DDL | À concevoir, non livré |
| A02, parcours déclarés et contexte transverse dans une baseline | Implémenté ; réception locale bornée, sans causalité inférée |
| A02, causalité inter-workflows/inter-dossiers et découverte sémantique | Non livré ; réception et liens explicites/versionnés nécessaires |
| A03, mapping AMASE | Enregistré pour discussion ; profil non intégré |
| A04, site statique navigable par dossier/sujet/diagramme | Implémenté ; réception locale dans le reçu associé |
| A04, graphe 2D dans chaque baseline et contexte de parcours | Implémenté ; réception locale bornée, sources exactes |
| A04, comparaison explicite de snapshots, validité et calendrier prévu | Implémenté ; réception locale bornée, sans historique de réception inféré |
| A04, atlas responsive et PWA sur le poste | Implémenté ; lecture directe et conservation locale explicite, voir le contrat et le reçu |
| A04, architecture story et trailers courts | Implémenté ; six chapitres exacts, lecture 24 s et trois MP4 BRAG reçus localement ; vidéos compagnons optionnelles |
| A04, vue fusionnée inter-dossiers et navigation générale du graphe par le temps | Non livré ; références et sémantique temporelle à expliciter |
| A04, 3D | Option à évaluer, non livrée |

Preuves : réception de l’incrément (document historique ou livrable local non inclus).
Suite : réception des parcours (document historique ou livrable local non inclus).
Graphe : réception 2D (document historique ou livrable local non inclus).
Dates : réception des comparaisons (document historique ou livrable local non inclus).
Présentation et PWA : [contrat](site-responsive-pwa.md) et
réception (document historique ou livrable local non inclus).
Récit et vidéos : [contrat](architecture-story.md) et
réception (document historique ou livrable local non inclus).
La distribution publique et les clients natifs ne sont pas requalifiés par ces
tests locaux. Les neuf cas métier Asteria restent des tests à exécuter après
construction ; leurs résultats ne sont pas fabriqués pour rendre la porte verte.
