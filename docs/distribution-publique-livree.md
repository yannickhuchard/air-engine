# Distribution publique livrée - 29 septembre 2026

Mise à jour du 30 septembre : identité développeur **Verified**, brouillon officiel
AIR 0.1.4 créé, fiche/logos/suggestions/notes enregistrés, deux skills téléversés
et reçus **Passed** par l’analyse OpenAI. D05 reste NOT_SUBMITTED : route MCP par installation à
résoudre, vidéo et tests du parcours public à fournir, attestations finales non
acceptées. Le constat actuel (document historique ou livrable local non inclus) remplace
le blocage d’identité décrit dans l’historique du 29 septembre ci-dessous.

Le [kit de réception publique](https://github.com/yannickhuchard/air-engine/blob/main/docs/reception-second-poste.md)
est publié comme asset supplémentaire de rc9, sans remplacer ses archives.
Sept tests locaux et une répétition complète sur ce poste passent, téléchargement
anonyme et inventaire du ZIP vérifiés. L’attestation d’un second poste et la recette
native restent non effectuées. Voir le reçu du lot (document historique ou livrable local non inclus).
La [demande OpenAI](https://github.com/yannickhuchard/air-plugin/blob/main/submission/openai-clarification.md)
et le [guide de démonstration](https://github.com/yannickhuchard/air-plugin/blob/main/submission/demo-runbook.md)
sont publics : demande envoyée au support OpenAI et escalade à un spécialiste
confirmée ; vidéo de recette du parcours public non réalisée. Le portail propose maintenant le téléversement ZIP,
remplaçant le constat initial MCP seul. L’éligibilité du fonctionnement local reste
en attente d’une réponse spécifique : reçu (document historique ou livrable local non inclus).

Deux [vidéos françaises du périmètre local](https://github.com/yannickhuchard/air-plugin/tree/main/videos)
sont désormais publiées : présentation de 2 min 01 s et parcours Asteria de
6 min 43 s, avec narration, sous-titres et kit de sources. Le parcours est un
montage de captures des vues réellement générées, pas une recette native ChatGPT.
Décodage des MP4, images des chapitres et téléchargements anonymes contrôlés :
reçu de livraison (document historique ou livrable local non inclus).

Le moteur [air-engine](https://github.com/yannickhuchard/air-engine) est public,
avec la [release 0.34.0rc9](https://github.com/yannickhuchard/air-engine/releases/tag/v0.34.0rc9).
Les 103 fichiers du moteur correspondent au snapshot rc9 reçu localement. La
reconstruction ajoute Apache-2.0, la documentation publique et les exemples ;
elle ne remplace pas la branche de développement 0.35 ni ses critères P10–P14.
Le dépôt de développement original reste privé.

Le [plugin 0.1.4](https://github.com/yannickhuchard/air-plugin/releases/tag/air-local-v0.1.4)
utilise désormais cette source publique et les guides Asteria. Ses sept tests de
packaging et les validateurs passent ; son téléchargement anonyme est vérifié.
Cette distribution ne constitue pas une soumission ni une approbation OpenAI.

## Exemples inclus

Les [trois dossiers Asteria](../fixtures/enterprise/asteria/README.md) restent dans
le même projet, avec briefs, données, socle partagé, baselines, scénarios et scripts.
Ils sont aussi inclus dans le dépôt public du moteur. La release propose un ZIP
des trois vues HTML calculées, avec reçu expurgé, LICENSE et NOTICE.

| Dossier fictif | Résultat conservé | Parcours de démonstration |
| --- | --- | --- |
| D01 SAV | UNKNOWN : confirmation ERP absente | PASS_SCOPED |
| D02 Atelier | VIOLATED : mesure périmée | PASS_SCOPED |
| D03 Identités | CONFLICTING : sources contradictoires | PASS_SCOPED |

Les trois portes restent BLOCKED. Trois tests Python synthétiques signés passent,
avec refus de falsification et révocation ; neuf tests des futurs systèmes métier
restent NOT_EXECUTED. Les révisions survivent à la restauration, qui révoque les
anciennes identités. Aucun ERP, atelier ou IAM réel n’est exécuté.

## Validation exacte

- Premier passage de la suite publique : **853 succès, 2 échecs de fichiers omis,
  2 skips**. Les deux dépendances manquantes de recette ont été réintégrées sous
  forme publique, sans modifier le noyau. **28 tests ciblés passent ensuite**.
  Aucun second passage complet n’est revendiqué.
- Export à liste de fichiers et empreintes : **12 tests passent** dans le projet
  de développement. Les chemins dangereux et les états non sélectionnés sont refusés.
- Wheel final : installation neuve/hors ligne, réinstallation sans perte et
  restauration reçues dans un environnement séparé, sur le même poste Windows.
- Clone Git anonyme et téléchargement des artefacts publics vérifiés ; chaque
  fichier de l’archive source correspond à son empreinte.
- Aucun test CI. Deux skips, absence de nouveau poste physique, autres OS,
  PostgreSQL et nouvelle recette native restent explicitement hors du reçu.

Les preuves sont dans public-engine-release-rc9.json (document historique ou livrable local non inclus)
et plugin-air-local-0.1.4.json (document historique ou livrable local non inclus).
Les artefacts publics portent leurs propres empreintes et ne réécrivent pas les
archives historiques rc9. Une mise à niveau entre deux versions publiques n’a pas
encore de version publique antérieure à tester.

## État des lots D01–D06

| Lot | État | Reste à faire |
| --- | --- | --- |
| D01 | Livré et vérifié dans le périmètre sélectionné | Pas d’ouverture de l’historique privé |
| D02 | Distribution initiale reçue localement | Autres plateformes et futures mises à niveau à qualifier |
| D03 | Connexion locale documentée ; voie annuaire non reçue | Accord OpenAI pour connexion par installation, authentification et recette native publique |
| D04 | Trois dossiers reçus en HTTP/MCP local | Rejeu dans le parcours public ChatGPT lorsque la route est disponible |
| D05 | Connexion au portail reçue ; création bloquée, NOT_SUBMITTED | Identité développeur vérifiée, route supportée, environnement de revue et soumission |
| D06 | Guides et support public livrés | Retour d’un architecte externe et extension des plateformes |

La connexion au portail est confirmée le 29 septembre. L’action « Create plugin »
ne propose que « With MCP » pour le compte observé. Elle affiche ensuite :
« You need a verified developer identity before you can create or upload a plugin. »
Aucun brouillon ni téléversement n’a donc pu être créé. Les paramètres
[Organization / General](https://platform.openai.com/settings/organization/general)
affichent désormais « Individual - Identity in review » après le contrôle
effectué par le titulaire. La création a été retestée et reste bloquée en attente
de l’approbation d’OpenAI ; aucune nouvelle action du titulaire n’est demandée.
Le constat (document historique ou livrable local non inclus) ne contient aucun identifiant privé.
Aucune identité vérifiée, attestation, approbation ou relation partenaire OpenAI n’est inventée.
Les huit cas de soumission restent des scénarios prévus ; les tests moteur ne les
remplacent pas. Les dépendances OpenAI empêchent la clôture intégrale de ces lots,
mais pas la distribution et l’utilisation locale du moteur public.
