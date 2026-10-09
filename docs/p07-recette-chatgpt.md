# Recette ChatGPT isolée pour P07

La connexion santé existante utilise `--access contribute`, qui masque les outils
d'engagement même si un mandat temporaire existe. Un rafraîchissement seul ne peut
pas rendre ces outils visibles. Les tester exige une connexion de recette isolée
avec `--access auto`, une identité propre et un mandat temporaire de découverte.
Les autorisations restent vérifiées à chaque appel.

## Préparer

```powershell
.venv/Scripts/python.exe scripts/p07_chatgpt_bench.py --root tmp/p07-chatgpt-final prepare
```

Choisir un répertoire neuf. Le banc crée sa SQLite privée, ses données Asteria
synthétiques et deux identités distinctes ChatGPT/Codex. Il ne modifie pas le pilote
métier. Les actions opérateur refusent un home externe ou une base redirigée.

Le lanceur `scripts/p07_chatgpt_tunnel.ps1` prend `-TunnelId`, `-Bench` et `-Runtime`.
Le lancer depuis la console où le précédent tunnel a été arrêté : il réutilise sa
clé en mémoire si elle est présente, sinon demande une saisie masquée. Ne jamais
passer une clé en argument, dans un prompt ou dans un fichier de recette.

Le lanceur convertit les chemins transmis à `--mcp.command` en séparateurs `/` :
le runtime du tunnel interprète les antislashs comme des échappements, y compris
entre guillemets. Après une mise à jour du lanceur, arrêter sa boucle avec Ctrl+C
et le relancer dans la même console pour charger la correction et conserver la clé
en mémoire. Modifier le fichier ne change pas la commande d'une boucle déjà lancée.

Le paramètre optionnel `-RestoreLauncher` désigne le lanceur du pilote à rétablir.
Après les essais, créer `restore-pilot.signal` dans le banc et arrêter uniquement
le runtime de recette identifié ; à la relance de la boucle, le lanceur initial
est rappelé avec la clé restée en mémoire. Vérifier l'identité pilote après retour.
Ne pas lancer deux pollers concurrents sur le même tunnel.

## Exécuter avec le client natif

1. Donner temporairement les mandats de découverte : action `grant-discovery`.
   Rafraîchir AIR dans les réglages ChatGPT et vérifier la présence des outils.
   Faire appeler `air_whoami` et `air_capabilities` depuis la conversation native.
2. Retirer les mandats avec `revoke-discovery`, puis faire appeler réellement
   admission et activation avec les références fictives prévues. Attendre les refus
   serveur, vérifier qu'aucun engagement n'est créé. Un outil masqué n'est pas un refus.
3. Faire lire les sources et objets autorisés/interdits, proposer et répéter une
   variante typée, introduire une référence invalide et lire la source hostile.
4. Exercer la politique retirée, l'expiration, la rotation et la coupure/reprise via
   les actions opérateur ; faire les lectures dans la même session native à chaque phase.
5. Soumettre, annuler deux fois, puis soumettre un nouveau job avec une nouvelle clé.
   Le banc `drain-jobs` exécute les calculs ; le client relit les états finaux.
6. Reprendre les références exactes déposées par Codex sans transférer sa conversation,
   puis faire reprendre par Codex les objets déposés par ChatGPT. Comparer les digests.

`p07_codex_chatgpt_handoff.py` produit la proposition côté Codex ; son statut
`PRODUCER_VERIFIED` ne reçoit pas le consommateur. `p07_codex_recovery.py` exerce
six phases dans un même thread natif ; `--recheck` recalcule les observations depuis
son journal sans relancer le client ni remplacer le rapport initial.

Pour vérifier le cycle de job natif Codex, conserver la réponse réelle à
`air_submit_job` dans un fichier privé directement dans le banc, puis transmettre
son nom à `p07_codex_approval.py --job-file`. Les approbations portent sur ce job
exact. `p07_codex_job_resume.py --cancelled-file` soumet une nouvelle clé deux fois,
lance `air worker-once` comme opérateur, puis fait relire les deux états par Codex.
Sous Windows, le worker doit être lancé depuis un module/fichier réel ; un lanceur
Python alimenté sur stdin ne convient pas au démarrage de ses sous-processus.

## Conserver et publier les preuves

Le processus de recette journalise les messages JSON-RPC dans `private-protocol/`,
répertoire protégé, avec expurgation du jeton courant et plafond de 64 Mio par session.
Cette capture complète est réservée au banc synthétique ; le journal `--trace` d'AIR
reste sans contenu pour les usages normaux. Aucun fichier brut n'entre dans Git.

Le catalogue est un instantané côté ChatGPT : redémarrer le serveur ou reconnecter
le compte ne prouve pas son actualisation. Vérifier explicitement que
`air_cancel_job`, `air_admission_admit` et `air_admission_activate` sont découverts
avant de retirer les mandats de recette. La procédure officielle est
[Plugins → connexion → Refresh](https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata).
Le bouton d'actualisation général du magasin de plugins ne suffit pas dans le
client de bureau observé. L'absence d'un outil ne devient pas un refus serveur.

Chemin effectivement utilisé le 28 septembre : **ChatGPT web → Plugins → AIR →
menu ⋯ → Manage → Refresh tools**, dans les paramètres de cette connexion.
Attendre sa fin puis refaire la recherche des outils dans le client natif.
Le tunnel doit être actif ; réinstaller AIR Local (les skills) n'actualise pas
la connexion MCP AIR. Ce chemin a débloqué les trois derniers essais, dont les
preuves complètes (document historique ou livrable local non inclus)
restent distinctes de l'actualisation elle-même.

Les messages du tunnel n'authentifient pas à eux seuls le client appelant. Corréler
les appels et résultats aux tours natifs ChatGPT, et séparer les appels opérateur.
Ne jamais remplacer des appels par le texte de réponse du modèle. Publier uniquement
les résumés expurgés, versions, contrôles et empreintes. Garder les phases incomplètes.

`scripts/p07_chatgpt_evidence.py <trace privée>` extrait les appels terminés et un
résumé sans arguments ni métadonnées du client. Sa fonction `native_window` accepte
seulement un tour natif terminé, sans erreur, et des appels entièrement compris dans
sa fenêtre temporelle. Conserver une copie immuable de la trace avant d'en épingler
l'empreinte ; ne pas épingler un fichier encore alimenté par le tunnel. La corrélation
temporelle complète l'observation du client, sans constituer une attestation indépendante.
