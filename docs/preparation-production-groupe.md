# Préparer AIR pour une transformation de groupe

Mise à jour du 28 septembre 2026 : **G1 est reçu pour le profil local AIR rc9**,
avec [décision et limites](g1-reception-locale.md), licence Apache-2.0 et
[support communautaire](support-local.md). P07 et P08 sont techniquement complets ;
Codex et ChatGPT sont les clients requis. Claude, la revue indépendante et la
réception sur un second poste physique restent hors des critères requis actuels.
Les anciennes preuves conservent leurs statuts historiques.

La production reçue concerne le poste de l'architecte : Windows 11, Python
3.12.14, SQLite et identité locale, dans le [périmètre publié](perimetre-local-supporte.md).
La taille du groupe n'impose pas un serveur partagé, PostgreSQL ou OIDC.
Les namespaces organisent les dossiers et les mandats ; ils ne synchronisent pas
les bases des différents architectes.

La branche 0.35.0.dev1 développe P10–P14 et **n'hérite pas** de la réception rc9.
Les nouveaux checkpoints signés sont une projection échangée explicitement ;
ils ne constituent pas une admission distribuée ni une synchronisation de modèles.

## Ordre des étapes restantes

1. **Déployer progressivement le profil rc9 reçu.** Utiliser les artefacts épinglés
   du reçu P08, accompagnés de [leur complément de licence](licence-rc9.md).
   Chaque entreprise désigne le responsable local, configure ses identités et
   mandats, vérifie ses sauvegardes et approuve l'usage de son agent cloud.
   Garder un périmètre limité et un retour arrière avant d'étendre à d'autres équipes.
2. **Conserver les validations différées comme telles.** Revue indépendante,
   second poste physique et mesures de prise en main en entreprise ne sont pas
   déclarés effectués. Leur report ne vaut pas un avis positif sur ces points.
3. **Achever P10–P14 et recevoir la nouvelle candidate.** Compléter noyau normatif,
   contrats et calculs, coordination multi-autorités, connecteurs et Workbench.
   Puis refaire les recettes applicables et recevoir chaque obligation du white paper
   pour G3. Voir les [incréments et limites](lot-normatif-increments.md) et la
   [roadmap](ROADMAP_PRODUCTION.md). Une fonction encore ouverte ne peut être
   promise au groupe au titre de G1.
4. **Plus tard, décider P09/G2.** Après adoption suffisante et décision explicite,
   qualifier la combinaison PostgreSQL/OIDC retenue, l'IdP réel, OAuth distant,
   PKI/proxy, sauvegarde et bascule si la haute disponibilité est requise.
   Les tests d'un backend ne reçoivent pas l'infrastructure centrale du groupe.

Les trois dossiers Asteria restent la non-régression de conception. Leurs diagnostics
et les neuf tests métier non exécutés sont conservés. AIR prépare les plans pour
la réalisation ultérieure ; les applications ERP, atelier et IAM futures ne sont
pas exécutées par cette réception.
