import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField

# Create your models here.

def knowledge_upload_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/knowledge_base/<uuid>.<ext>
    file_extension = filename.split('.')[-1]
    return f'knowledge_base/{uuid.uuid4()}.{file_extension}'

class KnowledgeDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(_("Document File"), upload_to=knowledge_upload_path)
    original_filename = models.CharField(_("Original Filename"), max_length=255, blank=True)
    status = models.CharField(
        _("Processing Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)
    processed_at = models.DateTimeField(_("Processed At"), null=True, blank=True)
    error_message = models.TextField(_("Error Message"), blank=True, null=True) # To store processing errors

    class Meta:
        verbose_name = _("Knowledge Document")
        verbose_name_plural = _("Knowledge Documents")
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.original_filename or str(self.id)

    def save(self, *args, **kwargs):
        if not self.original_filename and self.file:
            self.original_filename = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)


class DocumentChunk(models.Model):
    # Assuming usage of all-MiniLM-L6-v2 (384 dimensions)
    # Adjust dimensions if using a different embedding model.
    EMBEDDING_DIMENSIONS = 384

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name=_("Parent Document")
    )
    text_content = models.TextField(_("Text Content"))
    embedding = VectorField(_("Embedding"), dimensions=EMBEDDING_DIMENSIONS)
    metadata = models.JSONField(_("Metadata"), null=True, blank=True) # e.g., {'page_number': 1}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Document Chunk")
        verbose_name_plural = _("Document Chunks")
        indexes = [
            models.Index(fields=['document']),
            # Optional: Add a HNSW or IVFFlat index for faster vector search
            # Requires enabling the extension and running migrations
            # See django-pgvector docs for index types (e.g., HnswIndex)
            # HnswIndex(name='chunk_embedding_hnsw_idx', fields=['embedding'], opclasses=['vector_cosine_ops'], m=16, ef_construction=64)
        ]

    def __str__(self):
        return f"Chunk {self.id} from {self.document.original_filename or self.document.id}"
