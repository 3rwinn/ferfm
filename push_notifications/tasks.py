from django_q.tasks import async_task, schedule
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Notification, NotificationDelivery # Import your models
from .services import send_expo_push_messages, check_expo_push_receipts # Import your services

logger = logging.getLogger(__name__)

# Task to send a notification
def send_notification_task(notification_id):
    """ 
    Django Q task to send a specific notification.
    Calls the service function to handle the actual sending logic.
    """
    logger.info(f"Task: send_notification_task called for Notification ID: {notification_id}")
    try:
        send_expo_push_messages(notification_id)
        logger.info(f"Task: send_notification_task completed for Notification ID: {notification_id}")
    except Exception as e:
        logger.exception(f"Task: Error in send_notification_task for Notification ID {notification_id}: {e}")
        # Optionally, re-queue or mark notification as failed based on exception
        try:
            notification = Notification.objects.get(id=notification_id)
            if notification.status not in ['completed_success', 'completed_with_errors']:
                notification.status = 'failed'
                notification.save()
        except Notification.DoesNotExist:
            pass # Already logged in service
        except Exception as e_save:
            logger.error(f"Task: Failed to update notification status to failed for ID {notification_id}: {e_save}")

# Task to check receipts for a batch of delivery IDs
def check_receipts_batch_task(delivery_ids_batch):
    """
    Django Q task to check receipts for a batch of NotificationDelivery IDs.
    """
    logger.info(f"Task: check_receipts_batch_task called for batch of {len(delivery_ids_batch)} delivery IDs.")
    try:
        check_expo_push_receipts(delivery_ids_batch)
        logger.info(f"Task: check_receipts_batch_task completed for batch.")
    except Exception as e:
        logger.exception(f"Task: Error in check_receipts_batch_task: {e}")

# Periodic task to find deliveries needing receipt checks and queue batch tasks
# This task itself will be scheduled via Django Q Admin or a Schedule object in models/code
def poll_and_schedule_receipt_checks_task():
    """
    Periodically polls for NotificationDelivery records that need receipt checking
    and schedules check_receipts_batch_task for them in batches.
    """
    logger.info("Task: poll_and_schedule_receipt_checks_task started.")
    # Define a time window, e.g., deliveries sent more than 5 minutes ago and not yet checked
    # And not older than X days to avoid checking very old ones indefinitely
    time_threshold_past = timezone.now() - timedelta(minutes=5) 
    time_threshold_ancient = timezone.now() - timedelta(days=7) # Don't check receipts older than 7 days

    deliveries_to_check_ids = NotificationDelivery.objects.filter(
        status__in=['sent_to_expo', 'receipt_pending_check'], # Statuses indicating a ticket was likely obtained
        push_ticket_id__isnull=False,
        updated_at__lte=time_threshold_past, # Give some time for Expo to process
        updated_at__gte=time_threshold_ancient, # Avoid checking too old ones
        receipt_checked_at__isnull=True
    ).values_list('id', flat=True)

    if not deliveries_to_check_ids:
        logger.info("Task: No deliveries found needing receipt checks at this time.")
        return

    batch_size = 100 # Expo recommends chunks of 100 for get_receipts
    batches = [deliveries_to_check_ids[i:i + batch_size] for i in range(0, len(deliveries_to_check_ids), batch_size)]

    for batch_ids in batches:
        if batch_ids: # Ensure list is not empty
            logger.info(f"Task: Queuing check_receipts_batch_task for {len(batch_ids)} delivery IDs.")
            async_task('push_notifications.tasks.check_receipts_batch_task', list(batch_ids)) # Ensure it's a list
    
    logger.info("Task: poll_and_schedule_receipt_checks_task finished.")

# Convenience function to enqueue a notification for sending
def queue_notification_for_sending(notification_id):
    notification = Notification.objects.get(pk=notification_id)
    if notification.scheduled_at and notification.scheduled_at > timezone.now():
        logger.info(f"Scheduling notification ID {notification_id} for {notification.scheduled_at}")
        schedule(
            'push_notifications.tasks.send_notification_task',
            notification_id,
            schedule_type=schedule.ONCE,
            next_run=notification.scheduled_at,
            name=f"SendScheduledNotification-{notification_id}-"
                 f"{notification.scheduled_at.strftime('%Y%m%d%H%M%S')}" # Unique name
        )
        notification.status = 'scheduled'
    else:
        logger.info(f"Queuing notification ID {notification_id} for immediate sending.")
        async_task('push_notifications.tasks.send_notification_task', notification_id)
        notification.status = 'queued'
    notification.save() 