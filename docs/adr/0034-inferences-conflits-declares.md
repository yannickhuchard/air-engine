# ADR 0034 - Inférences et conflits déclarés

Statut : adopté, tranche 17. Source : A.2 page 44 et B.1 du white paper.

Inference et Conflict sont des objets DRAFT versionnés. Le sous-profil utilise uniquement des Assertions comme énoncés de conflit ; la portée commune doit être un même Scope exact, avec intersection non vide des validités. Les situations nécessitant une algèbre de recouvrement de scopes différents sont refusées dans ce binding initial. La raison textuelle décrit le conflit sans en démontrer automatiquement la sémantique.

Une inférence conserve la conclusion, les prémisses et sa dérivation. Les cycles conclusion → prémisses sont refusés dans une baseline fermée. Les expressions sont validées par le moteur pur existant et leurs littéraux Reference participent à la fermeture ; aucune correspondance automatique entre texte d’assertion et valeur calculable n’est introduite. L’ordre des ensembles de prémisses et d’assertions est canonique, l’ordre des opérandes de l’AST est conservé.

La lecture d’un dossier est une projection de baseline avec une date de validité demandée. Elle expose les risques de prémisses et les dates sans modifier les états. Une décision associée à un conflit ne vérifie pas la nouvelle situation. Les preuves ne sont ni téléchargées ni qualifiées automatiquement. Une nouvelle révision peut enregistrer la décision en conservant la déclaration initiale et toutes les assertions.

Cette tranche ne reçoit pas intégralement AIR-V009 à AIR-V013 et ne permet pas ESTABLISHED. Les règles de fermeture déjà qualifiées sont étendues aux deux nouveaux types. Les domaines de connaissance plus larges et les transitions de qualification nécessitent leurs propres contrats et preuves.
