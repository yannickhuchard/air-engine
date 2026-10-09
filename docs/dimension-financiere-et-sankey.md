# Dimension financière et Sankey standards

Incrément du 5 octobre 2026. Chaque Projet d’architecture généré, y compris les dossiers sans budget, présente une synthèse financière et un accès précoce à la traçabilité. Une absence de déclaration reste un manque visible, pas un montant nul ou un lien inventé.

## Contrat financier

Le sujet 17, les documents Markdown et les pages HTML utilisent la même projection déterministe `air.financial-view/1`. Chaque dossier expose `finance.html` et `finance.json`, avec baseline exacte et empreinte. Les appels CLI et MCP de compilation produisent ces mêmes résultats, sans paiement ni modification comptable.

`CostItem.calculation` contient des `parts` : `label`, `quantity`, `unit`, `unit_price`, `explanation`. Leur somme quantité × prix unitaire doit égaler exactement `amount.value` avant arrondi. Les `sources` sont des références exactes à Source ou Assertion ; `evidence_status` distingue ASSUMPTION, DOCUMENTED_QUOTE et RECORDED_COST. Ces statuts sont déclarés et ne certifient pas l’authenticité des pièces.

La nature CAPEX/OPEX et les catégories restent des classifications de planification. CONTINGENCY est le poste explicite de contingence ; le compte comptable légal doit être attribué avec le comptable de l’organisation. La contingence documente assiette, taux et conditions de libération. Elle est distincte de la marge restant dans une enveloppe et du relais de TVA.

L’affectation facultative `allocation` distingue ENGINEERING, HARDWARE, STARTUP, OPERATIONS, CONTINGENCY et OTHER. Un `FinancialPlan` déclare sa période, ses `cost_items`, l’enveloppe programme, la réserve de trésorerie TVA, sa base et ses sources. Les devises sont identiques dans un plan, sans conversion implicite. Les coûts récurrents du plan ont une fin explicite et tous ses coûts appartiennent à sa période.

`reference_status=APPROVED_REFERENCE` exige une `approval_source`. `funding_status` reste indépendant ; une approbation de référence ne confirme ni fonds disponibles ni autorisation d’achat. Un scénario de revenu mensuel peut être déclaré avec sa base. Son déficit d’exploitation est calculé seulement si les affectations des postes sont renseignées ; les recettes hypothétiques ne réduisent jamais l’enveloppe à financer.

Les anciens CostItems restent valides. Leur détail indique précisément les calculs absents. Sans fin, un poste récurrent utilise 36 mois inclusifs, signalés comme hypothèse. Le précédent calcul employait seulement 25 mois malgré son texte : ce défaut est corrigé. Une période explicite prévaut ; les sommes par devise, période et catégorie sont séparées. Les calculs utilisent Decimal dans un contexte local stable.

## Contrat de traçabilité

`traceability.html` fournit un Sankey local SVG, son filtre par exigence, les chemins textuels et leurs preuves. `traceability.json` conserve la baseline, l’empreinte, les objets exacts, les champs référencés et les statuts déclarés. Aucun CDN, outil Node ou service externe n’est nécessaire pour utiliser le site.

La première colonne distingue Requirement fonctionnelle et exigences de qualité/contrainte, dont QualityRequirement. Les fonctions `satisfies` et les blocs `functions` établissent les joins fonctionnels. ConstructionUnit.justified_by fournit une autre justification explicite. Les ComplianceMappings applicables lient les exigences de qualité aux implémenteurs déclarés ; un PLANNED reste PLANNED. Les implémenteurs pris en charge sont blocs, unités, composants et équipements via leurs références. Les mappings vers des zones/connexions sans chemin vers un bloc exploitable restent un manque visible.

Une unité rejoint un bloc par fonction réalisée ou par co-réalisation explicite dans un RuntimeComponent. Partager un bloc ne suffit pas à attribuer un livrable fonctionnel sans fonction pertinente ou justification. Les sorties `ConstructionUnit.outputs` portent des produits, services, documents, campagnes ou reporting selon leur `kind` déclaré ; leur emplacement est cité. Un RuntimeComponent rejoint sa cible prévue par `realizes` et par un Environment déclaré PRODUCTION. Aucun de ces liens ne prouve l’exécution du produit futur.

Chaque exigence applicable représente une unité, répartie en fractions exactes entre ses chemins. Les flux agrégés conservent ces valeurs. Les largeurs ne représentent ni argent, ni effort, ni performance, ni couverture qualifiée. Les exclusions NOT_APPLICABLE déclarées sont listées avec leurs mappings. Les liens absents créent des ruptures explicites. Les noms identiques et les révisions différentes ne sont pas fusionnés.

Au-delà de 250 nœuds, le graphique global laisse place aux chemins textuels et à la projection complète, sans tronquer les données. Plus de 20 000 chemins provoquent une erreur bornée et invitent à découper le dossier. Les budgets habituels d’export restent appliqués.

## Décision UX

L’accueil présente deux synthèses : « Comprendre l’investissement » et « Du besoin à ce qui sera livré ». La navigation permanente et les six parcours donnent un accès direct aux détails. Le Sankey complet possède sa page de focus dans les premières destinations : cela évite de charger l’accueil avec un graphe dense, tout en faisant de la traçabilité une lecture standard.

Cette décision provient de la revue experte et des parcours de l’audit UX existant, pas d’une séance inventée avec participants. Le COMEX lit d’abord enveloppe, durée, contingence et état du financement ; les équipes ouvrent calculs, chemins et références. Sur mobile, la synthèse reste compacte et le Sankey dispose d’un défilement interne au clavier. Les listes sources fonctionnent sans JavaScript ; le filtre est une amélioration progressive. Les transitions respectent le mouvement réduit et les couleurs suivent le branding du dossier. Une certification d’accessibilité et une réception avec utilisateurs restent distinctes.

## ProxiBot

L’approbation reçue est conservée dans `projects/proxibot/docs/approbation-budget-reference-2026-10-05.md`. Les 32 postes sont décomposés sans changer leurs montants : notamment six robots × 30 000 EUR, chargeurs, batteries, kits, fret groupé, droits en sensibilité, livraison au dépôt, jours d’ingénierie et charges de six mois. Tous les prix et compositions de lots restent des hypothèses sans devis OEM.

Le programme calculé est 729 256.80 EUR, contingence 99 382.80 EUR comprise ; la marge dans l’enveloppe programme est 20 743.20 EUR. Enveloppe programme 750 000 EUR + relais TVA 100 000 EUR = 850 000 EUR de référence approuvés. L’ouverture d’une seule zone et les dates illustratives restent explicites. Les fonds, assurances, permis, choix OEM, calibration et revue ne sont pas fabriqués.
