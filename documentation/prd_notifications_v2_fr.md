# Document des Exigences Produit (PRD) : Système de Notifications Push Backend (v2)

**1. Introduction & Objectifs**

* **Introduction :** Ce document décrit les exigences pour un système de notifications push au sein du backend. Ce système permettra d'envoyer des notifications aux utilisateurs d'applications mobiles via Expo Push Notifications. Il s'inspire d'un précédent système de notification plus complexe mais simplifié pour les besoins actuels.
* **Objectifs :**
  * Permettre aux administrateurs de créer et d'envoyer/programmer manuellement des notifications diffusées à tous.
  * Envoyer automatiquement une notification chaque fois qu'un nouvel élément "Actu" (actualité/mise à jour) est créé.
  * Délivrer de manière fiable les notifications à tous les jetons push Expo enregistrés et actifs.
  * Fournir un mécanisme pour gérer les jetons qui ne sont plus valides (par exemple, application désinstallée).
  * Gérer les notifications et l'enregistrement des jetons via l'interface d'administration Django.
* **Indicateurs de Succès :**
  * Taux de livraison élevé des notifications aux jetons actifs.
  * Notification automatique réussie lors de la création d'une `Actu`.
  * Capacité de l'administrateur à gérer les notifications et à visualiser l'état de livraison de base.

**2. Aperçu de l'Architecture du Système**

Le système consistera en une nouvelle application Django (par exemple, `push_notifications`) gérant l'enregistrement des jetons, la gestion des notifications et l'interaction avec le service Expo Push Notification. Des tâches de fond gérées par `django-q2` seront utilisées pour envoyer les notifications et vérifier les accusés de réception.

```mermaid
graph TD
    subgraph Application Cliente
        A[Application Mobile] -- 1. Envoi Jeton Expo --> B[/api/push_notifications/register-token/];
    end

    subgraph Système Backend
        B -- 2. Stockage/Mise à jour Jeton --> C[(Table ExpoPushToken)];
      
        subgraph Actions Administrateur
            D[Administrateur] -- 3a. Création/Programmation Notification --> E{Admin Django};
            E -- 4a. Sauvegarde & Mise en file/Programmation --> F(File django-q2);
        end

        subgraph Déclencheur Automatique
            G[App Actu] -- 3b. Nouvelle 'Actu' Créée (Signal) --> H{Service de Notification};
            H -- 4b. Création Notification & Mise en file Envoi --> F;
        end

        subgraph Traitement en Arrière-plan
            I(Worker django-q2) -- 5. Interroge File/Planification --> F;
            I -- 6. Exécute send_notification_task --> J(Service Expo Push);
            J -- 7. Envoie Notification --> K[Appareils Utilisateurs];
            J -- 8. Retourne Tickets Push --> I;
            I -- 9. Stocke Tickets --> L[(Table NotificationDelivery)];
      
            M(Worker django-q2 - Périodique) -- 10. Exécute poll_and_schedule_receipt_checks --> L;
            M -- 11. Met en file check_receipts_task --> F;
            I -- 12. Exécute check_receipts_task --> J;
            J -- 13. Retourne Accusés --> I;
            I -- 14. Met à jour Statut Livraison --> L;
            I -- 15. Désactive Jetons Invalides (via enregistrement Livraison) --> C;
        end
    end

    style "Application Cliente" fill:#lightgrey,stroke:#333,stroke-width:2px
    style "Système Backend" fill:#lightblue,stroke:#333,stroke-width:2px
    style "Actions Administrateur" fill:#f9f,stroke:#333,stroke-width:2px
    style "Déclencheur Automatique" fill:#cfc,stroke:#333,stroke-width:2px
    style "Traitement en Arrière-plan" fill:#ccf,stroke:#333,stroke-width:2px
```

**3. Fonctionnalités Détaillées**

* **3.1. Enregistrement de Jeton Push Expo (Anonyme)**
  * Un point d'API permettra aux clients mobiles d'enregistrer leur jeton push Expo.
  * Aucune authentification utilisateur n'est requise pour ce point d'API.
  * Le système stockera le jeton. Si un jeton existe déjà, son horodatage `updated_at` et son statut `is_active` (mis à True) devront être mis à jour.
* **3.2. Création de Notification (Manuelle via Admin)**
  * Les administrateurs peuvent créer des notifications avec un titre, un corps et une charge utile de données JSON optionnelle.
  * Les notifications sont initialement sauvegardées comme 'Brouillon'.
  * Les administrateurs peuvent choisir d'envoyer une notification 'Brouillon' immédiatement ou de la programmer pour une date/heure future.
* **3.3. Création de Notification (Automatique lors de la création d'une `Actu`)**
  * Lorsqu'un nouvel objet `Actu` est sauvegardé dans l'application `actus` :
    * Un nouvel objet `Notification` sera automatiquement créé.
    * Le corps de la `Notification` sera dérivé du contenu de l'objet `Actu` (par exemple, `Actu.text`).
    * Le titre de la `Notification` peut être une chaîne prédéfinie (par exemple, "Nouvelle Mise à Jour !").
    * Cette notification sera mise en file pour un envoi immédiat.
* **3.4. Envoi de Notification (Programmé & Immédiat)**
  * Les notifications marquées pour envoi immédiat (manuelles ou automatiques) sont mises en file via `django-q2`.
  * Les notifications programmées sont gérées par le mécanisme de planification de `django-q2`.
  * La tâche d'envoi récupérera tous les `ExpoPushToken` actifs et leur enverra le contenu de la notification via l'API Expo.
  * Des enregistrements `NotificationDelivery` seront créés pour chaque jeton auquel la notification est envoyée, stockant l'ID du ticket push reçu d'Expo.
* **3.5. Vérification des Accusés de Réception**
  * Une tâche de fond périodique interrogera Expo pour les accusés de réception en utilisant les ID de tickets push stockés.
  * Les enregistrements `NotificationDelivery` seront mis à jour avec le statut de l'accusé (`ok`, `error`) et tous les détails.
* **3.6. Désactivation de Jeton**
  * Si un accusé de réception Expo indique `DeviceNotRegistered` (ou une erreur permanente similaire), l'`ExpoPushToken` correspondant sera marqué comme `is_active = False` pour éviter d'autres tentatives d'envoi vers ce jeton invalide.

**4. Modèles de Base de Données (dans l'application `push_notifications`)**

* **`ExpoPushToken`:**
  * `token`: `CharField(unique=True)` - La chaîne du jeton push Expo.
  * `is_active`: `BooleanField(default=True, db_index=True)` - Indique si le jeton est considéré comme actif.
  * `created_at`: `DateTimeField(auto_now_add=True)`
  * `updated_at`: `DateTimeField(auto_now=True)`
* **`Notification`:**
  * `title`: `CharField` - Titre de la notification.
  * `body`: `TextField` - Contenu principal de la notification.
  * `data`: `JSONField(null=True, blank=True)` - Charge utile JSON optionnelle pour le client.
  * `status`: `CharField` avec des choix (par exemple, `draft`, `queued`, `scheduled`, `sending`, `sent`, `partially_failed`, `failed`, `completed_with_errors`).
  * `creator`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)` - Administrateur qui l'a créée (nul si générée par le système).
  * `scheduled_at`: `DateTimeField(null=True, blank=True)` - Heure pour l'envoi programmé.
  * `sent_at`: `DateTimeField(null=True, blank=True)` - Horodatage du début du processus d'envoi.
  * `created_at`: `DateTimeField(auto_now_add=True)`
  * `updated_at`: `DateTimeField(auto_now=True)`
* **`NotificationDelivery`:**
  * `notification`: `ForeignKey(Notification, on_delete=models.CASCADE, related_name='deliveries')`
  * `expo_push_token`: `ForeignKey(ExpoPushToken, on_delete=models.CASCADE, related_name='deliveries')`
  * `push_ticket_id`: `CharField(null=True, blank=True, db_index=True)` - ID du ticket Expo.
  * `status`: `CharField` (par exemple, `pending_send`, `sent_to_expo`, `expo_error`, `receipt_pending_check`, `receipt_ok`, `receipt_error`). Statut initial après l'envoi à Expo.
  * `receipt_checked_at`: `DateTimeField(null=True, blank=True)`
  * `receipt_status`: `CharField(null=True, blank=True)` - Statut de l'accusé de réception Expo (`ok`, `error`).
  * `receipt_details`: `JSONField(null=True, blank=True)` - Détails de l'accusé de réception Expo.
  * `created_at`: `DateTimeField(auto_now_add=True)`
  * `updated_at`: `DateTimeField(auto_now=True)`

**5. Points d'API**

* **Enregistrer le Jeton Push :**
  * **Chemin :** `/api/push_notifications/register-token/`
  * **Méthode :** `POST`
  * **Authentification :** Aucune.
  * **Description :** Enregistre ou met à jour un jeton push Expo.
  * **Corps de la Requête :** `{"expo_push_token": "ExponentPushToken[...]"}`
  * **Réponse Succès :** `200 OK` ou `201 Created` avec `{"success": true, "message": "Jeton enregistré/mis à jour."}`
  * **Réponses Erreur :** 400 (Mauvaise Requête - par exemple, format de jeton invalide), 500.

**6. Interface d'Administration (`admin.py`)**

* **`ExpoPushTokenAdmin`:**
  * Affichage liste : `token`, `is_active`, `created_at`, `updated_at`.
  * Champs de recherche : `token`.
  * Filtres : `is_active`.
  * Actions : Marquer manuellement les jetons comme actifs/inactifs.
* **`NotificationAdmin`:**
  * Affichage liste : `title`, `status`, `creator`, `scheduled_at`, `sent_at`, `created_at`.
  * Champs de recherche : `title`, `body`.
  * Filtres : `status`, `creator`, `scheduled_at`.
  * Inlines : `NotificationDeliveryInline` (lecture seule, affichant jeton, statut, receipt_status).
  * Actions d'Administration Personnalisées :
    * "Mettre en file les notifications brouillons sélectionnées pour envoi" : Change le statut à `queued`, crée une tâche `django-q2`.
    * "Programmer les notifications brouillons sélectionnées" : Si `scheduled_at` est défini, change le statut à `scheduled`, crée une planification `django-q2`.
* **`NotificationDeliveryAdmin`:** (Principalement pour visualisation/débogage, lié depuis `NotificationAdmin`)
  * Affichage liste : `notification`, `expo_push_token`, `status`, `push_ticket_id`, `receipt_status`, `updated_at`.
  * Recherche : `push_ticket_id`, `expo_push_token__token`.
  * Filtres : `status`, `receipt_status`.

**7. Tâches d'Arrière-plan (`tasks.py` utilisant `django-q2`)**

* **`send_notification_task(notification_id)`:**
  * Récupère l'objet `Notification`.
  * Récupère tous les `ExpoPushToken` actifs.
  * Construit les messages et les envoie en utilisant `expo-server-sdk-python`.
  * Crée/met à jour les enregistrements `NotificationDelivery` avec les ID de tickets et le statut initial.
  * Met à jour le statut de `Notification` (par exemple, à `sending`, puis `sent` ou `failed`).
* **`poll_and_schedule_receipt_checks()` (Tâche Périodique) :**
  * Programmée pour s'exécuter périodiquement (par exemple, toutes les 15-30 minutes).
  * Trouve les enregistrements `NotificationDelivery` qui ont un `push_ticket_id`, ont été envoyés il y a > X minutes, et dont les accusés n'ont pas été vérifiés (`receipt_checked_at` est nul).
  * Met en file des tâches `check_receipts_batch_task` par lots pour ces livraisons.
* **`check_receipts_batch_task(delivery_ids_batch)`:**
  * Prend un lot d'ID `NotificationDelivery`.
  * Appelle une fonction de service pour récupérer les accusés d'Expo pour les tickets correspondants.
  * Met à jour les enregistrements `NotificationDelivery` avec le statut/détails de l'accusé.
  * Si `DeviceNotRegistered`, marque l'`ExpoPushToken` associé comme inactif.

**8. Mécanisme de Déclenchement pour la création d'`Actu`**

* Un signal Django (`post_save`) sera connecté au modèle `Actu` (dans l'application `actus`).
* Lorsqu'une nouvelle instance `Actu` est créée (`created=True` dans le gestionnaire de signal) :
  * Une fonction de service `create_and_queue_actu_notification(actu_instance)` sera appelée.
  * Ce service va :
    1. Créer un objet `Notification` (par exemple, titre "Nouvelle Mise à Jour !", corps depuis `actu_instance.text`).
    2. Mettre en file la tâche `send_notification_task` pour cette nouvelle notification.

**9. Hors Périmètre/Non-Goals (pour cette version)**

* Vues de notification spécifiques à l'utilisateur dans l'application.
* Fonctionnalité "Marquer comme lu".
* Compteurs de notifications non lues pour les utilisateurs.
* Ciblage des notifications vers des jetons individuels spécifiques (tous les envois sont des diffusions).
* Segmentation complexe des utilisateurs pour les notifications.

**10. Hypothèses**

* `django-q2` est installé et configuré pour les tâches d'arrière-plan.
* `expo-server-sdk-python` sera utilisé pour la communication avec Expo.
* Le modèle `Actu` existe dans une application nommée `actus` et possède un champ `text`.
* Les utilisateurs administrateurs font partie du système d'authentification standard de Django.
