# Sécurité et support d'AIR

AIR est actuellement une candidate de qualification. Aucune version n'est encore
reçue pour la production d'un groupe, et aucune durée de support de production ou
SLA de correction n'est engagée. Consulter `docs/etat-implementation.md` et
`docs/validation.md` pour distinguer ce snapshot de développement de rc9.

## Signaler et traiter une vulnérabilité

Transmettre le signalement au propriétaire du dépôt et au responsable sécurité de
l'installation par leur canal privé approuvé. Ne pas ouvrir de ticket public avec
des secrets, modèles d'architecture confidentiels, jetons ou journaux bruts. La
désignation de ces responsables et de leur canal est un préalable du pilote P08.

Fournir version/commit et empreinte de l'artefact, topologie, conditions de
reproduction sur une installation jetable et impact observé, avec les données
sensibles remplacées. Le responsable sécurité doit qualifier l'exposition et
décider des restrictions temporaires, rotations d'identités ou suspensions de
service adaptées. Ne pas effectuer d'essai destructif sur une base métier.

Une correction doit disposer d'un test de régression, passer la matrice applicable
et recevoir de nouveaux artefacts et empreintes. Documenter les versions affectées,
les mesures transitoires, la procédure de mise à niveau et son retour à sauvegarde.
Le responsable de l'installation organise la diffusion de l'avis et vérifie le
déploiement. Aucun de ces actes humains n'est réputé accompli par une CI verte.

## Fin de support et décision de mise en service

Avant G1/G2, fixer les versions supportées, la période, le contact d'astreinte ou
de support, les délais selon la gravité et le préavis de fin de support. Une version
abandonnée doit être explicitement identifiée dans le dossier de décision, avec
chemin de migration testé, archivage des preuves et responsabilité de maintien.
Ces engagements restent ouverts ; les candidates ne sont pas des versions LTS.

Pour la première production sur poste, le pilote P08 reçoit la revue de sécurité indépendante,
la conservation et la protection des sauvegardes ainsi que les accès des agents. Le chiffrement
AIR reste une option selon la politique applicable. Le cycle des certificats serveur et l'IdP réel
concernent les déploiements qui les utilisent, différés vers P09/G2 pour la plateforme centrale.
La journalisation sans contenu libre ne remplace pas la revue de sécurité.
