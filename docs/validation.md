# Validation de la distribution publique

Version : 0.34.0rc9. Le reçu `public-validation.json` joint à la release identifie
les résultats et les empreintes exactes de cette distribution. Consulter ce reçu
avant d’attribuer une qualification à une archive. La réception de référence portait
sur Windows 11, Python 3.12.14 et SQLite/local. Cette reconstruction publique ne
réécrit pas les archives historiques.

La recette publique couvre les tests moteur inclus, l’installation du wheel dans
un environnement neuf, la réinstallation, la restauration et les trois dossiers
Asteria. La validation native d’un nouveau compte ChatGPT, un second poste physique,
macOS/Linux, PostgreSQL, l’approbation d’annuaire et la conformité AIR complète restent
hors de ce reçu. Aucune CI n’est lancée.

Le kit de [réception sur un second poste](reception-second-poste.md), ajouté le
30 septembre, a été répété sur le poste de développement dans une venv neuve :
artefacts rc9 téléchargés, installation/reprise et trois dossiers PASS_SCOPED.
Sept tests ciblés du kit passent (empreintes altérées, destination existante,
preuves incomplètes et absence d’attestation artificielle). Ce reçu supplémentaire
ne modifie pas les archives rc9 et n’atteste pas un second appareil ni un client natif.
