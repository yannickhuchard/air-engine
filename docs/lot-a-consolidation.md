# Lot A : consolidation du périmètre local public

Candidate : sources publiques AIR 0.35, SQLite, authentification locale,
Python seul pour installer et consulter le dossier. Ce lot ne réouvre pas
les prérequis historiques Claude ou la validation indépendante différée.

## Critères de réception

- Suite locale complète sur les sources candidates, avec skips et limites explicites.
- Trois parcours Asteria DEMO-METIER-1 sur installation isolée.
- Paquet exact : installation neuve hors ligne, réinstallation, mise à niveau
  depuis rc9 et restauration avec anciennes identités révoquées.
- Site et nouvelle barre reçus localement sur les quatre largeurs et sans JS.
- Workflows Codex et ChatGPT observés réellement sur le catalogue courant :
  identité, version, lecture exacte, diagnostic, proposition, reprise et livraison.
- Distribution publique et guides cohérents avec le périmètre effectivement reçu.

Les contrôles HTTP/MCP ne remplacent pas les appels natifs. Une indisponibilité
cliente reste ouverte avec sa cause et sa procédure de reprise. Aucun PASS
n’est produit depuis une affirmation de l’assistant. Claude Code, Cursor et
Antigravity peuvent être documentés mais ne sont pas requis dans cette réception.

Pas de CI pendant le lot. Pas de données ProxiBot privées dans la distribution.
Les simulations et revues du dossier ProxiBot ne sont pas qualifiées par ce lot.

## Réception du 10 octobre 2026

**Lot A terminé dans le périmètre local public défini ci-dessus.** La version
reste 0.35.0.dev1 ; cette réception technique ne transforme pas tous les profils
AIR en normes reçues et ne qualifie pas une plateforme centralisée.

| Contrôle | Résultat observé |
| --- | --- |
| Régression publique locale | 1 176 succès, 1 skip explicite du helper privé ProxiBot, 0 échec |
| Retouches finales du site et de la recette native | Rejeu ciblé public : 20 succès ; complément privé : 21 succès |
| Démonstration Asteria | DEMO-METIER-1 : trois dossiers reçus dans leur portée de design ; neuf scénarios métier historiques restent non exécutés |
| Site | Trois dossiers, 84 diagrammes ; barre reçue sur 24 vues, quatre largeurs avec/sans JS ; dossier local non distribué sur huit vues |
| PWA | 649 ressources, consultation hors ligne, mise à jour explicite et échec de mise à jour conservant le snapshot |
| Distribution | Deux builds identiques ; source publique et wheel, sans dossier privé |
| Installation | Paquet exact, environnement neuf, installation hors ligne après collecte des dépendances, réinstallation conservant identité/révisions |
| Mise à niveau/reprise | rc9 vers 0.35.0.dev1, conservation des données ; retour au snapshot rc9 ; restauration révoquant les anciens jetons |
| Poste Windows | Contrôles techniques et seuils synthétiques reçus, dix cycles ; revue indépendante différée |
| Codex 0.159.2 | Lecture, refus d’accès, proposition, reprise, annulation idempotente avec approbation par l’opérateur agent, capsule et livrables observés |
| ChatGPT | Connexion AIR existante rafraîchie, 15 appels corrélés aux deux conversations : lecture, diagnostic, proposition rejouée, reprise et compilation |

La régression complète précède les dernières retouches UI ; les vingt tests
ciblés sont rejoués ensuite. Les premières tentatives et erreurs de recette
restent dans les traces privées : catalogue obsolète, mauvais registre dans
l’ancienne recette d’annulation, clé de version mal lue par un contrôleur.
Les constats reçus reposent sur les réponses natives et le registre, pas sur
le verdict écrit par un assistant. L’annulation est maintenant épinglée au
serveur MCP local de test, avec approbation demandée par outil.

La découverte automatique d’un projet Codex non approuvé n’est pas qualifiée.
Le client reçoit sa configuration MCP pour l’invocation de recette ; aucune
configuration globale ni protection n’est désactivée. Le plugin public de
skills et la connexion native ChatGPT restent distincts d’une acceptation dans
l’annuaire OpenAI. Les autres clients/OS, le second poste physique et la
validation indépendante ne sont pas déduits de ce lot. Aucune CI lancée.

Voir [le reçu structuré](traceability/lot-a-2026-10-10.json) et
[le choix UX](ux-barre-completude.md).
