import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from .models import KnowledgeDocument

logger = logging.getLogger(__name__)

@receiver(post_save, sender=KnowledgeDocument)
def trigger_document_processing(sender, instance, created, **kwargs):
    """
    Listens for newly created KnowledgeDocument instances with PENDING status
    and triggers the background processing task.
    """
    if created and instance.status == KnowledgeDocument.Status.PENDING:
        logger.info(f"New KnowledgeDocument detected (ID: {instance.id}). Enqueuing processing task.")
        # Enqueue the task
        async_task(
            'knowledge_base.tasks.process_document', # Path to the task function
            instance.id, # Argument for the task function
            q_options={'group': f'doc_proc_{instance.id}'} # Optional: Group task, useful for tracking/limits
        )
    elif not created and instance.status == KnowledgeDocument.Status.PENDING:
        # Optional: Handle cases where an existing document is manually reset to PENDING?
        # Be careful to avoid infinite loops if the task itself fails and resets status.
        logger.info(f"KnowledgeDocument (ID: {instance.id}) status set to PENDING. Re-enqueuing processing task.")
        # You might want extra checks here before re-enqueuing
        async_task(
            'knowledge_base.tasks.process_document', 
            instance.id,
            q_options={'group': f'doc_proc_{instance.id}'} 
        ) 