from django.contrib import admin
from .models import KnowledgeDocument, DocumentChunk

# Register your models here.

@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'status', 'uploaded_at', 'processed_at')
    list_filter = ('status', 'uploaded_at')
    search_fields = ('original_filename',)
    readonly_fields = ('uploaded_at', 'processed_at', 'status', 'error_message')
    # We make status readonly here because it should be updated by the processing task

    # Optional: Add an action to trigger reprocessing
    def reprocess_documents(modeladmin, request, queryset):
        for doc in queryset:
            # Trigger your background task here, e.g.:
            # process_document_task.delay(doc.id)
            doc.status = KnowledgeDocument.Status.PENDING
            doc.error_message = None
            doc.processed_at = None
            doc.save()
    reprocess_documents.short_description = "Reprocess selected documents"
    actions = [reprocess_documents]


# Optional: Register DocumentChunk for debugging, but likely not needed for regular admin use
@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'created_at', 'metadata')
    list_filter = ('document',)
    raw_id_fields = ('document',)
    readonly_fields = ('created_at', 'embedding') # Embedding is too large to display nicely
    search_fields = ('text_content',)
