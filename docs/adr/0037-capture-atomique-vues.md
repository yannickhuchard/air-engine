# ADR 0037 - Capturer atomiquement les produits de vue

Statut : accepté pour le binding expérimental air.view/0.20.

Le type View du white paper relie Viewpoint, Baseline, ToolchainSpec et deux ArtifactRef. Le rendu pur de tranche 19 ne suffisait pas à conserver ce produit avec une provenance historique. La capture devient un service transactionnel, sans nouvelle table ni dépendance externe.

View reste extérieur aux profils de baseline de données pour éviter une source qui dépend de son rendu. Son namespace provient du Viewpoint. Les deux manifestes, leurs octets, le View, les gardes de contexte et les reçus d’identité/idempotence sont écrits ensemble après recontrôle des droits. La répétition relit la capture historique et ne remplace jamais son générateur par la version actuelle.

Les artefacts de capture portent un format 0.20 exigeant une garde vers la baseline et le View exacts. Les chemins de lecture d’artefacts contrôlent aussi cette baseline, y compris les dépendances hors namespace. Une garde perdue ferme l’accès. Les artefacts historiques 0.18 restent compatibles, sans élargissement de leur contrat.

La ToolchainSpec relève les fichiers d’implémentation au démarrage ; elle n’est pas une signature ni une attestation distante. Les vérificateurs de reprise contrôlent les produits conservés sans les régénérer. Les imports de brouillons ne peuvent fabriquer un View capturé ; les transferts complets préservent les reçus et gardes.
