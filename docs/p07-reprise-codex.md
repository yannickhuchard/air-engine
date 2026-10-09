# P07 : passation actualisée le 28 septembre 2026

**État courant après changement de périmètre :** Claude n'est plus requis ; revue
indépendante et second poste physique sont différés. Les sections suivantes conservent
l'historique. La découverte Codex, la proposition idempotente, sa reprise, le refus
d'admission/activation après révocation et la double annulation avec approbation précise
passent maintenant. Voir les preuves courantes (document historique ou livrable local non inclus).

ChatGPT appelle réellement `air_whoami`, `air_capabilities` et `air_get`, via une
conversation native accessible par les outils de l'application. Son catalogue courant
n'expose pas annulation/admission/activation ; l'écran verrouillé bloque sa remise à jour
par Computer Use. Restent la suite native ChatGPT complète, les parcours de sécurité,
la reprise Codex ↔ ChatGPT et leur consolidation IDE-01..10. La confiance du projet Codex
est déjà approuvée ; ne pas redemander cette action. Le [pilote P08](lot-pilote-local.md)
a passé ses exercices locaux, mais dépend toujours de cette réception P07.

Ce document permet de reprendre sans l'historique de conversation. Les secrets restent dans le home privé
du banc ; aucun jeton n'est cité ici. Les résultats et leurs limites sont dans
la traçabilité initiale (document historique ou livrable local non inclus) et le
complément sur le moteur corrigé (document historique ou livrable local non inclus).
Le complément du 28 septembre (document historique ou livrable local non inclus) conserve
le diagnostic Codex et les nouveaux essais Claude. Aucun succès historique n'est réécrit.

## Banc et moteurs

- **Banc** : `tmp/p07-claude-session/` (non versionné).
  - Home privé `.air-p07`, SQLite, API locale sur le port 49453, sans worker intégré.
  - Démarrage : `python scripts/p07_session_bench.py --root tmp/p07-claude-session act start-server`.
  - Arrêt : même commande avec `stop-server`.
- **Identités** (rôle éditeur, lecture des namespaces Asteria et `example.claims`, écriture sur `example.claims`) :
  - `p07-session-claude-code`, adaptateur dans `workspace/` ;
  - `p07-session-codex`, adaptateur dans `workspace-codex/` ;
  - namespace interdit : `p07.other`.
- **Moteur testé par la session Claude** : commit `a8f5d39`, source
  `570e80d68fc11bdd887a9c2795e998a3e979654c17a50e7c7efa5be292094bf8`.
  Son processus MCP date d'avant les corrections.
- **Moteur corrigé** (`86608ca`) : source `1db6acf3bc3589ea54c70b021fb3cb0ed517c76f59d2c454f0c5c3e852964e02`,
  `mcp.py` `0737e729cd7c50aaa04a1ea8562f877c28f50a315da50cffdfa92f7cbf32158c`.
  Codex et la nouvelle session Claude l'ont chargé pour le complément.

## Références persistantes

| Objet | Identifiant | Rév. | Empreinte |
| --- | --- | --- | --- |
| Baseline de départ | `urn:p07:session:baseline` | 1 | `sha256:3074fd982915287a48c0289d18d191e827141866dd3e2d3c1898cbe242595991` |
| Source citée | `urn:asteria:source:company` | 1 | `sha256:68adbb601ce390af14de162b6e4780c32a5f3ebcd2fdd77af3e7f9cbb89b4143` |
| Portée variante | `urn:air:example:scope:claims` | 2 | `sha256:909b7a940bd2dc88e193ee6120f4352b9c1e332fbf2ce324684ad62553df9b6b` |
| ChangeSet proposé | `urn:p07:session:change:claims-notification` | 1 | `sha256:01a460bec58e4616aa66c39fe339476ab2b14acc23977864df73858b239c1062` |
| Baseline candidate | `urn:air:baseline:proposal:01a460bec58e4616aa66c39fe339476ab2b14acc23977864df73858b239c1062` | 1 | `sha256:f87f2b27d795e18b82336b0444e050cd6ca82c1918e91547fa47c20ddf72b8f7` |
| Job annulé | `urn:air:job:605aaa82f0b152c3321ddf709cc990dca96c1a806ad9cff1a589ccf351363884` | | `sha256:6ff007e554c0d59d425b2edf6dd7a9f6de26cdb3555aea5f450549742fd47c53` |
| Job recalculé | `urn:air:job:15ed8489a455c9996346a7ed4f2a54e7a956c751f8bbd823a14c66a9ce607070` | | `sha256:902400fc4e5a42764f28a062c276aec616b883c6ac00e6c9ea39ddd9497f4afb` |

La proposition n'est ni approuvée ni publiée. Le job recalculé est `SUCCEEDED`, avec un résultat
VIOLATED et aucune réservation.

## Déjà fait

- **Session native Claude Code 2.1.281.**
  - PASS : IDE-01, 02, 03, 04, 06, 08, 09.
  - PARTIAL : IDE-05, 07, 10.
  - Parcours : expiration et rotation dans le même processus.
  - Coupure : échec initial conservé ; correction requalifiée dans une nouvelle session Claude.
- **Reprise Claude → Codex** (`codex-cli 0.155.0-alpha.9.2`).
  - Identité distincte, empreintes du ChangeSet et de la candidate identiques.
  - Vérifiée depuis le journal brut Codex.
  - Limite : MCP fourni à l'invocation, lecture seule.
- **Dossier assemblé** : `tmp/p07-claude-session/evidence-6/` (privé), avec une copie expurgée dans
  `docs/traceability/p07-claude-session/`. `client-reception-check` renvoie **INCOMPLETE** (18 lacunes, code 2).
- **Nouvelle session Claude Desktop Code**, dans le même workspace déjà approuvé : découverte et
  lecture natives, `AIR_UNREACHABLE` pendant l'arrêt API, mêmes identité et digest après reprise.
- **Reprise Codex → Claude**, proposition non approuvée et non publiée :
  - ChangeSet `urn:p07:codex:handoff:change:e0187977ebef4856be8c134a449eb953`, révision 1,
    digest `sha256:3ce18e5a1051db2ccb12c14875532a231022f9c10b7ac6896737eb821b33d635` ;
  - candidate `urn:air:baseline:proposal:3ce18e5a1051db2ccb12c14875532a231022f9c10b7ac6896737eb821b33d635`,
    révision 1, digest `sha256:029c2747a556bea5148aad125359c55e418dedb5eb8115055748faab845daa13`.
  - Preuves privées `codex-to-claude-final/`, journal natif Claude figé dans `followup-transcript-snapshots/`.
    Les deux tentatives précédentes restent conservées avec leurs défauts de fixture.
- **Codex, catalogue conservé après révocation** : refus 403 natifs d'admission et d'activation,
  aucun engagement créé, droits du banc restaurés (`codex-stale-catalog/`).
- **25 tests locaux passent** ; aucune CI. Le moteur n'a pas changé pendant ce complément.
- **28 septembre : dix contrôles supplémentaires passent dans Claude**, sur le moteur corrigé :
  annulation répétée sans effet, nouvelle clé et nouveau calcul terminé, source hostile sans
  élévation, diagnostic de référence manquante identique via le client, l'API et la CLI.
  Le job annulé garde `attempt=0`, le nouveau termine sans réservation. **32 tests locaux passent**.

## Reste à faire, par qui

1. **Codex, sur ce poste.**
   - **Projet approuvé le 28 septembre, sur autorisation explicite de l'utilisateur.** Seule la clé
     de confiance de `D:\development\air\tmp\p07-claude-session\workspace-codex` est ajoutée.
     `config/read` confirme désormais `PROJECT_CONFIG_LOADED` et `codex mcp get air` trouve le serveur
     actif. Ne plus demander cette approbation. L'essai natif suivant ne voit toutefois aucun outil AIR
     local ; il reste INCOMPLETE. Preuve (document historique ou livrable local non inclus).
   - Diagnostiquer la découverte des outils à l'exécution, puis rejouer
     `python scripts/p07_native_discovery.py --root tmp/p07-claude-session
     --output tmp/p07-claude-session/discovery-after-trust` (sur une seule ligne, sortie neuve).
     Le précontrôle doit trouver le MCP local actif ; les deux appels natifs doivent ensuite
     confirmer la bonne identité et la version. La seule présence de la configuration ne suffit pas.
   - Exécuter le rapport Codex IDE-01..IDE-10, dont l'annulation avec approbation interactive.
2. **Claude, sur ce poste.**
   - Compléter IDE-05/10 avec des appels natifs refusés : le profil contributeur retire ces outils,
     ce qui ne constitue pas une tentative refusée par le serveur. Ne pas remplacer cette preuve
     par les refus obtenus avec Codex.
   - Recevoir la suite complète sur le moteur corrigé ; les sept cas historiques sont épinglés
     à la source précédente. La nouvelle session a déjà reçu coupure/reprise et Codex → Claude.
3. **Décisions.** L'existence d'identifiants hors mandat (403 contre 404), et la publication de
   `air_admission_propose` et `air_renewal_propose` à un éditeur.
4. **Hors de ce poste.**
   - Connecteur ChatGPT (429 précédemment ; le connecteur distant accessible à Codex répond 404
     pendant ces compléments, y compris le 28 septembre). La commande **Reconnect**, puis
     **Connect AIR**, ont été exécutées dans l'interface ChatGPT par Computer Use sur demande
     explicite de l'utilisateur. L'appel distant `air_whoami` suivant retourne HTTP 429 sans
     identité AIR. **Transport rétabli ensuite le 28 septembre** : le serveur pilote et le runtime
     du tunnel étaient arrêtés ; après relance et saisie locale de la clé par l'utilisateur,
     `air_whoami` et `air_capabilities` réussissent via le connecteur distant depuis Codex
     (sujet `fraud-architect`, moteur `0.34.0rc9`).
     Preuve (document historique ou livrable local non inclus).
     Reste à recevoir la suite depuis ChatGPT lui-même avec une identité dédiée P07.
   - Revue par une personne distincte avec sa propre identité.
   - Échange explicite entre deux postes physiques.

Assembler un nouveau dossier dans un dossier de sortie neuf avec `scripts/p07_session_evidence.py`
(`--codex-resume` pour la reprise). Ne pas mélanger les preuves du moteur testé avec celles du moteur corrigé.
