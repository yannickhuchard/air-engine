# ADR 0032 - Cibles métier explicites

Statut : adopté et implémenté dans la tranche 15. Références : Goal et Metric, A.2 page 44 ; capacités et services, A.3 page 45.

Le white paper nomme TargetSpec et exige unité et contexte sans détailler ce record. Le sous-profil air.business/0.15 utilise un identifiant local, une Metric exacte, un opérateur EQ/LTE/GTE, une valeur typée AIR-Expr, une unité et un Scope exact. Les identifiants locaux sont uniques dans le Goal. La Metric de chaque cible doit figurer dans measures ; son unité doit correspondre à celle de la cible.

Les premières valeurs sont scalaires : Boolean, Decimal et Quantity. Boolean et Decimal sont sans dimension, notés par l’unité 1. Les quantités utilisent leur unité AIR-Expr exacte ; aucune conversion implicite n’est réalisée. Les valeurs inconnues ou contradictoires restent visibles et ne deviennent pas des cibles satisfaites. Une fenêtre optionnelle de Metric utilise PT<n>S, en secondes entières positives sans zéro initial, au plus 366 jours. La fenêtre demandée doit avoir exactement cette durée.

L’observation peut pointer exactement la Metric. Le moteur évalue seulement la cible structurée et le signal explicitement associé ; il ne déduira ni formule d’agrégation ni adéquation de population depuis les textes definition, aggregation ou population. La couverture PARTIAL du signal demeure une limite du résultat.

Intent, Stakeholder, Concern, Capability, BusinessService et Product sont des objets DRAFT reliés aux types existants. Les références optionnelles à des types non livrés restent vides dans ce sous-profil ou empêcher une baseline fermée. La responsabilité déclarée d’une partie prenante ne modifie aucune politique d’autorisation.

Les profils et empreintes historiques sont conservés. Les résultats de comparaison restent distincts d’une réception métier et ne déclenchent aucune action externe.

Les seuils connus, inconnus ou contradictoires sont des entrées typées internes issues du Goal enregistré. Ils ne sont jamais construits comme littéraux incertains dans l’AST, ni acceptés en surcharge par le client. La combinaison des 32 cibles maximales est un arbre AND équilibré ; une erreur d’exécution reste une erreur globale et les résultats individuels ne sont pas masqués.
