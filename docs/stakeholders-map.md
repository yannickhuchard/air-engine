# Stakeholders Map

La carte des parties prenantes est le livrable standard **38-stakeholders-map**.
Elle est générée avec le dossier et disponible depuis l'accueil, la navigation,
les parcours de lecture et la checklist documentaire. Une page de diagramme,
le Markdown et `stakeholders.json` conservent les mêmes sources versionnées.
Source candidate : moteur `0.35.0.dev7`, plugin `0.1.14`, non publiés par cet incrément.

## Ce que la carte doit permettre de décider

- Qui contribue déjà à ce projet et pourquoi ?
- Qui est identifié mais doit encore être mobilisé ?
- Quels rôles manquent et comment les pourvoir ?
- De quoi chaque personne ou groupe est-il responsable dans ce projet ?
- Quels composants, exigences, décisions ou livrables dépendent de sa contribution ?

La vue regroupe les contributions : **Impliqués**, **À mobiliser**, **Manquants**,
**À préciser**. Ce choix met en évidence les actions de mobilisation. Un diagramme
d'influence/intérêt demanderait des évaluations que le modèle ne possède pas ;
ces scores ne sont pas inventés. Les liens vers le projet ne dessinent pas une
hiérarchie d'autorité. Le RACI déclaré complète les responsabilités spécifiques.

Le design reprend les couleurs et les polices du site. Chaque carte sépare le
rôle, la personne et l'action de lecture ; le rôle sélectionné reste marqué.
Des libellés explicites accompagnent les repères colorés. La carte se réorganise
selon la place disponible, sans canevas horizontal à déplacer sur téléphone.
Sur un écran large, une fiche se place à côté de la carte ; sur téléphone,
la sélection ouvre une vue dédiée à cette fiche. Un bouton ramène au rôle
sélectionné en conservant les filtres et la recherche.

Les filtres par état et la recherche locale par rôle, personne ou responsabilité
se combinent. La recherche ignore les accents. Un résultat vide permet de
réinitialiser les filtres. Toutes les contributions sont présentes dans les
limites du budget de projection ; aucune limite visuelle de 80 entrées n'est
ajoutée. Les noms longs ne sont plus tronqués.

Les ancres et les liens vers les sources restent utilisables. Sans script,
toutes les fiches sont ouvertes et les commandes inactives sont masquées.
L'impression inclut toutes les fiches. Une courte transition accompagne la
sélection, sans animation automatique et avec respect du mouvement réduit.
Aucun service externe n'est requis. L'[exercice UX/UI](ux-stakeholders-map.md)
et la recette navigateur ne constituent pas une étude de terrain.

## Modéliser une participation

`air.StakeholderParticipation` complète les objets existants Stakeholder, Actor,
Role, OrganizationUnit et RaciAssignment, sans modifier leurs anciennes révisions.

| Champ | Sens |
| --- | --- |
| `scope` | Périmètre exact du projet d'architecture |
| `role` | Rôle attendu et ses responsabilités générales |
| `stakeholder` | Partie prenante, acteur ou organisation exacts, lorsque identifiés |
| `state` | INVOLVED, TO_INVOLVE ou MISSING |
| `reason` | Pourquoi cette contribution est nécessaire pour ce projet |
| `responsibilities` | Ce que la partie prenante doit prendre en charge dans le projet |
| `architecture_links` | Exigences, blocs, décisions, projets ou autres objets concernés |
| `engagement_plan` | Prochaine action de mobilisation et contexte |
| `coordination_owner` | Identité déclarée responsable de cette mobilisation |
| `staffing_action` | NONE, ASSIGN, RECRUIT, PARTNER ou ASSESS |
| `needed_by` | Date facultative de participation attendue |

INVOLVED et TO_INVOLVE exigent une partie prenante exacte. MISSING porte un
rôle vacant et interdit d'inventer une identité affectée. Il faut alors déclarer
une affectation interne, un recrutement, un partenaire ou un mode à décider.
INVOLVED n'annonce pas une nouvelle action de staffing. Une date impossible et
un lien de la participation vers elle-même sont refusés.

Les anciens rôles et parties prenantes restent visibles avec l'état de projection
UNASSESSED, « À préciser », si aucune participation n'est documentée. L'absence
d'affectation ne devient pas automatiquement un recrutement. Les acteurs logiciels,
machines et robots ne sont pas ajoutés automatiquement à l'inventaire humain ;
une participation explicite peut néanmoins les référencer comme tels.

Les responsabilités générales du rôle et celles propres au projet sont affichées
séparément. Le RACI est joint par le rôle exact, avec sa phase et ses activités.
Les liens de participation complètent le graphe d'architecture via les mêmes
références typées que le reste du modèle.

## Utiliser les mêmes données dans chaque client

`air_stakeholders_map` ou `air stakeholders-map requete.json` prend :

```json
{
  "baseline": {"id": "urn:example:baseline", "revision": 1, "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
  "content": "JSON"
}
```

Remplacer les valeurs d'exemple par la baseline réelle. `content: HTML` ajoute
une représentation HTML avec SVG à la projection. L'API correspondante est
`POST /v1/stakeholders/map`. Le service reste en lecture seule et vérifie les
droits de lecture de la fermeture exacte. CLI, API et MCP partagent le service.

Décrire le type avec `air_describe_type`, préparer et valider les participations
par le parcours habituel, puis régénérer les livrables. Le plugin et les skills
expliquent cette démarche. En mode portable sans moteur, préparer les drafts,
sans annoncer les contrôles exécutés. La régénération actualise la carte ; une
page exportée n'est pas synchronisée en direct.

Une carte complète signifie que les contributions et besoins sont documentés,
pas que les personnes ont accepté, qu'une embauche est faite ou qu'un mandat
exécutable est accordé. Les noms fictifs d'une recette ne deviennent pas des
parties prenantes réelles de l'entreprise. Une carte peut documenter des rôles
vacants dans un design prêt pour une réalisation ultérieure.

## Recette locale

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_stakeholders.py --basetemp tmp/pytest-stakeholders-local
.venv/Scripts/python.exe scripts/demo_delivery_assurance.py --stakeholders --output tmp/demo-stakeholders-local
```

La recette fictive présente un architecte impliqué, une référente sécurité à
mobiliser, un responsable exploitation à recruter et un rôle d'accessibilité
dont la participation reste à préciser. Aucune embauche, invitation ou action RH
n'est exécutée. Les trois dossiers Asteria DEMO-METIER-1 restent une vérification
distincte de la non-régression. Aucun déclencheur CI n'est activé.
