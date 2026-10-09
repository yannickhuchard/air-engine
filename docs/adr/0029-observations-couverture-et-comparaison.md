# ADR 0029 - Observations d’exploitation et couverture explicite

Statut : accepté pour air.runtime/0.12, sous-profil de développement. Source : white paper A.12 p.52 et ScopeCoverage cité pp.44/51/52.

Le white paper nomme ScopeCoverage sans fournir ses champs détaillés. Le binding initial choisit scope, included, excluded, completeness=PARTIAL et limitations. Ces champs sont un choix d’implémentation identifié, pas une citation normative. Les références exactes incluses/exclues sont typées et fermées ; un même objet ne peut apparaître dans les deux ensembles. Le scope de couverture est le sujet observé.

RuntimeObservation accepte initialement un Scope comme sujet et un nom de signal textuel. Les variantes RuntimeInstance et Metric nécessitent leurs types propres, encore absents. La valeur est soit un TypedValue AIR-Expr validé, soit un ArtifactRef localisé et empreinté. Un artefact n’est ni téléchargé ni interprété implicitement. Les fenêtres sont finies et non vides ; les valeurs UNKNOWN et CONFLICTING restent distinctes.

Drift et Incident conservent les champs et références du catalogue. Une référence de traitement vers Contribution/Decision ne peut pas encore fermer une baseline, ces types restant à implémenter. Les types sont DRAFT. Une résolution textuelle d’incident ne prouve pas son efficacité.

L’ingestion authentifiée fixe source, observations et reçu dans la même transaction. Le texte recorded_by reste une provenance déclarée ; l’auteur authentifié est dans le registre d’audit et le reçu. Les fenêtres futures sont refusées à l’ingestion. Le service de brouillons reste disponible pour préparer des modèles incomplets.

La comparaison est pure et utilise une interprétation AIR-Expr fournie explicitement par l’appelant. Elle ne prétend pas compiler correctement une exigence libre ni qualifier cette interprétation. Elle vérifie types, fenêtre, fraîcheur et référence effective des entrées ; les données inéligibles deviennent inconnues, jamais disponibles par défaut. Le résultat ne modifie aucune attente, ne crée pas automatiquement une Drift et ne déclenche aucune remédiation.

Les profils foundation/0.2 et construction/0.4 conservent leurs types autorisés. Une nouvelle baseline runtime/0.12 est nécessaire pour inclure les nouveaux objets ; les empreintes historiques restent stables.
