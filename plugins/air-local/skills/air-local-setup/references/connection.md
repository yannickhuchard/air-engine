# Connexion par entreprise et par projet

La configuration MCP reste dans le référentiel de travail, hors du plugin partagé.
Le moteur et les données ne doivent pas être placés dans le cache du plugin : une
mise à jour ou désinstallation du plugin ne doit pas les supprimer.

## Codex et Claude Code

Lire `docs/distribution.md` et `docs/lot-atelier-claude-code.md` du moteur. Utiliser
les schémas de la version installée. Une requête `ide-setup` contient :

```json
{
  "client": "codex",
  "workspace": {"name": "Architecture", "organization": "Entreprise cible"},
  "server": {
    "interpreter": "C:/AIR/.venv/Scripts/python.exe",
    "home": "C:/AIR-donnees/entreprise/.air",
    "credential": "architecte.json",
    "port": 8740
  },
  "access": "read-only"
}
```

Ces valeurs sont un exemple, pas une installation détectée. Adapter les chemins,
le port et l'identité à l'installation retenue. `credential` est un nom de fichier,
jamais son contenu. `contribute` convient si l'utilisateur demande l'édition et
dispose des droits correspondants ; le serveur reste responsable des autorisations.

Avec le Python du moteur :

```text
python -m air --home <home> ide-setup <requete.json> --workspace <referentiel>
python -m air --home <home> ide-setup <requete.json> --workspace <referentiel> --apply
```

La première commande montre le plan ; résoudre les conflits de génération avant
application. Codex ne charge la configuration que pour un projet approuvé selon
ses règles de confiance. Ne pas désactiver ces règles. Claude Code utilise le
même générateur avec `client: claude-code` ; sa réception P07 n'est plus requise.
Les autres IDE ont leurs formats propres décrits dans `docs/distribution.md`.

## ChatGPT

Le processus MCP local stdio n'est pas directement une connexion ChatGPT distante.
Suivre `docs/integrations-ide.md` et les instructions courantes de la plateforme
pour la connexion MCP via tunnel sécurisé. Chaque installation garde sa propre
connexion et son identité ; ne jamais distribuer celle du développeur AIR.
Le plugin de skills peut accompagner cette connexion, sans la créer ni remplacer
son authentification. Un tunnel privé n'est pas une publication dans l'annuaire public.

Si un outil attendu manque : comparer version et capacités avec le catalogue
effectivement visible ; utiliser la découverte des outils différés si disponible.
Un outil absent n'est pas un refus du serveur. Actualiser la connexion côté client
suivant sa documentation puis ouvrir une nouvelle conversation ; vérifier réellement
le nouveau catalogue. Ne pas prétendre que redémarrer le moteur suffit.

## Changer de client freelance

Séparer le home, l'identité, le namespace et le référentiel de chaque entreprise.
Vérifier l'identité et une baseline connue après chaque changement. Aucun paramètre
global du plugin ne doit rediriger silencieusement tous les projets vers un client.
Le plugin n'assure ni fédération ni synchronisation interentreprises.
