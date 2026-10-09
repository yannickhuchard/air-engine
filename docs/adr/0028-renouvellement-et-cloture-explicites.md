# ADR 0028 - Renouvellement et clôture des engagements locaux

Statut : accepté pour le binding local 0.11 ; pas de transaction distribuée.

Une admission fige un contenu et ses réservations. Le renouvellement engage seulement une nouvelle tête d’autorisation après proposition et revue exactes. Il reprend le calendrier et les quantités initiaux, recontrôle les offres actuelles en excluant les propres réservations et compare une génération. Le registre conserve toute la chaîne des reçus. Cette séparation évite de libérer puis recréer les mêmes ressources ou de modifier le planning sous une ancienne approbation.

La fin d’un épisode est une déclaration distincte, avec Evidence épinglée et revue indépendante. Sa réception marque l’épisode clos ; elle ne libère pas automatiquement les ressources. La libération explicite est refusée si un épisode de cette admission reste ouvert. Un travail jamais activé dont la réservation est libérée est annulé, pas achevé.

Les lectures et transferts conservent générations, épisodes et reçus. Une importation incohérente entre projection d’autorisation, chaîne de renouvellement ou marqueur de clôture est refusée. La restauration n’accorde aucun nouveau mandat.

Ce binding ne prouve ni présence humaine, ni exécution d’un système externe, ni pertinence sémantique automatique d’une preuve. Les équipes responsables doivent qualifier leurs déclarations et mandats. L’avancement partiel et la réallocation de travail actif demandent des contrats distincts.
