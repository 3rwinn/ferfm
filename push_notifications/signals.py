from django.db.models.signals import post_save
from django.dispatch import receiver
from actus.models import Actu # Assuming your Actu model is here
from .services import create_and_queue_actu_notification_service
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Actu)
def actu_post_save_receiver(sender, instance, created, **kwargs):
    """
    Listens for new Actu instances being saved and triggers a notification.
    """
    if created:
        logger.info(f"Signal: Actu object ID {instance.id} created. Triggering notification service.")
        try:
            create_and_queue_actu_notification_service(instance)
        except Exception as e:
            # Catching exceptions here to ensure signal handling doesn't crash the save operation
            logger.exception(f"Signal: Error calling notification service for Actu ID {instance.id}: {e}")
    # else:
        # logger.info(f"Signal: Actu object ID {instance.id} updated, not sending notification.") 