# Clôture technique locale P07/P08 - 28 septembre 2026

**P07 et le pilote technique P08 sont terminés dans le périmètre local décidé.**
Le dossier P07 complet (document historique ou livrable local non inclus)
contient **10/10 cas Codex, 10/10 cas ChatGPT et six parcours transversaux requis**.
Les contrôles P07 (document historique ou livrable local non inclus) et
P08 (document historique ou livrable local non inclus) retournent
`LOCAL_TECHNICAL_EVIDENCE_COMPLETE`, sans anomalie. **28 tests locaux ciblés passent**
(extracteur de traces, réception cliente et dépendance P08). Aucune CI lancée.

## Derniers essais exécutés

Le serveur et le tunnel du banc fictif ont été relancés. L'actualisation effective
se trouve dans ChatGPT web : **Plugins → AIR → ⋯ → Manage → Refresh tools**.
Réinstaller le plugin seul n'avait pas actualisé le catalogue de cette connexion.
Cette action a rendu les trois outils manquants disponibles dans le client natif.

- **IDE-05** : admission sans mandat refusée, `AIR_FORBIDDEN`, HTTP 403.
- **IDE-10** : activation depuis le catalogue conservé après retrait du mandat,
  refusée avec le même code. Aucune activation créée.
- **IDE-09** : le premier appel annule le job, le second ne change rien. Un nouveau
  calcul utilise une nouvelle clé ; sa répétition ne crée pas de doublon. Après un
  passage du worker, les lectures natives donnent ancien job CANCELLED et nouveau
  job SUCCEEDED.

Le résultat de conception du nouveau calcul reste **VIOLATED**, avec un manque de
4 FTE-semaines. SUCCEEDED signifie que le calcul a abouti, pas que l'architecture
satisfait les contraintes. Aucun effet métier externe, aucune réservation ni
autorisation créée. Les droits temporaires de découverte sont retirés.

La preuve complémentaire (document historique ou livrable local non inclus)
relie les réponses JSON-RPC aux fenêtres des tours natifs. Elle distingue les gestes
opérateur : actualisation, retrait des mandats, approbation cliente **Allow once**
du seul essai négatif d'activation et lancement du worker. La réponse narrative du
client affirmait à tort qu'aucune approbation n'avait eu lieu ; elle n'est pas utilisée
comme preuve de ce point. Aucune permission globale n'a été élargie.

## Versions et limites de la clôture

La qualification est cumulative : ChatGPT dans OpenAI.Codex **26.915.4065.0** pour les
premiers cas, **26.924.2738.0** pour IDE-05/09/10. La version exécutée est indiquée
par cas. Tous les essais n'ont pas été rejoués sur la dernière version cliente.
Les versions et surfaces Codex restent celles de leurs reçus d'origine.
Le moteur **0.34.0rc9 est inchangé**, identique aux sources LF de l'archive qualifiée.
Le dossier partiel antérieur est conservé intégralement dans son répertoire historique.

P08 conserve les preuves d'installation hors ligne, réinstallation, mise à niveau,
restauration, retour arrière et les trois dossiers Asteria ; sa dépendance P07 est
maintenant satisfaite. Les neuf scénarios métier non exécutés de ces dossiers ne
sont pas transformés en tests réussis.

La validation indépendante, la réception entre deux postes physiques et **G1 restent
différés**, conformément à la décision utilisateur. Les contrôleurs ne signent pas
une réception indépendante : leurs champs `p07_received` et `production_ready`
restent false. Ils ne sont pas modifiés pour obtenir artificiellement une signature.
Cette clôture ne prétend ni une conformité intégrale au white paper, ni un serveur
central multi-entreprise qualifié, ni une synchronisation automatique entre postes.
