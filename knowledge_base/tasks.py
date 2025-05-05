import logging
import os
from io import BytesIO

from django.utils import timezone
from django.db import transaction
from django.conf import settings

# Text Extraction
from pypdf import PdfReader
import docx # python-docx

# Text Chunking
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Embeddings
from sentence_transformers import SentenceTransformer

# Models
from .models import KnowledgeDocument, DocumentChunk

logger = logging.getLogger(__name__)

# --- Constants ---
# Choose your embedding model
# Make sure the model name matches one compatible with sentence-transformers
# and that its dimensions match DocumentChunk.EMBEDDING_DIMENSIONS
# e.g., 'all-MiniLM-L6-v2' (384 dims), 'all-mpnet-base-v2' (768 dims)
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
# Consider loading the model once globally if tasks run in the same process space,
# but loading per-task ensures isolation, especially with multiple worker types.
# sentence_model = SentenceTransformer(EMBEDDING_MODEL_NAME) # Potential global load

# Chunking parameters (tune based on your content and embedding model context window)
CHUNK_SIZE = 1000 # Characters
CHUNK_OVERLAP = 150 # Characters overlap between chunks


def extract_text_from_pdf(file_content):
    """Extracts text from PDF file content (bytes)."""
    text = ""
    try:
        reader = PdfReader(BytesIO(file_content))
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise # Re-raise to mark task as failed
    return text

def extract_text_from_docx(file_content):
    """Extracts text from DOCX file content (bytes)."""
    text = ""
    try:
        doc = docx.Document(BytesIO(file_content))
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        raise # Re-raise to mark task as failed
    return text


def process_document(document_id):
    """
    Django-Q task to process an uploaded KnowledgeDocument:
    1. Extracts text.
    2. Chunks text.
    3. Generates embeddings.
    4. Saves chunks and embeddings to the database.
    """
    logger.info(f"Starting processing for KnowledgeDocument ID: {document_id}")
    try:
        doc = KnowledgeDocument.objects.get(id=document_id)
    except KnowledgeDocument.DoesNotExist:
        logger.error(f"KnowledgeDocument with ID {document_id} not found. Task cannot proceed.")
        return # Or raise an exception if preferred

    # --- Prevent reprocessing if already completed/failed unless forced ---
    # (Add logic here if you want to prevent reprocessing based on status)
    # if doc.status in [KnowledgeDocument.Status.COMPLETED, KnowledgeDocument.Status.FAILED]:
    #     logger.warning(f"Document {document_id} already processed with status {doc.status}. Skipping.")
    #     return

    doc.status = KnowledgeDocument.Status.PROCESSING
    doc.processed_at = None
    doc.error_message = None
    doc.save(update_fields=['status', 'processed_at', 'error_message'])

    try:
        file_content = doc.file.read()
        filename = doc.original_filename.lower()

        # --- 1. Extract Text ---
        logger.info(f"Extracting text from {filename}...")
        if filename.endswith('.pdf'):
            extracted_text = extract_text_from_pdf(file_content)
        elif filename.endswith('.docx'):
            extracted_text = extract_text_from_docx(file_content)
        else:
            raise ValueError(f"Unsupported file type: {doc.original_filename}")

        if not extracted_text.strip():
            raise ValueError("No text could be extracted from the document.")

        # --- 2. Chunk Text ---
        logger.info("Chunking extracted text...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
        )
        text_chunks = text_splitter.split_text(extracted_text)
        logger.info(f"Created {len(text_chunks)} text chunks.")

        if not text_chunks:
             raise ValueError("Text splitting resulted in zero chunks.")

        # --- 3. Generate Embeddings ---
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
        # Load model within the task for better isolation / memory management per task
        sentence_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device='cpu') # Force CPU if GPU issues arise
        logger.info("Generating embeddings for chunks...")
        embeddings = sentence_model.encode(text_chunks, show_progress_bar=False) # Set True for debug if needed

        # --- 4. Save Chunks ---
        # Delete old chunks first if reprocessing is allowed
        # DocumentChunk.objects.filter(document=doc).delete()

        logger.info("Saving document chunks and embeddings...")
        chunks_to_create = []
        for i, chunk_text in enumerate(text_chunks):
            chunk = DocumentChunk(
                document=doc,
                text_content=chunk_text,
                embedding=embeddings[i].tolist(), # Convert numpy array to list for DB
                # Add metadata if needed, e.g., chunk index or page number if available
                # metadata={'chunk_index': i}
            )
            chunks_to_create.append(chunk)

        # Use transaction.atomic to ensure all chunks are saved or none are
        with transaction.atomic():
            # Clear existing chunks if this is a re-processing run
            # Be careful with this if multiple tasks could run for the same doc
            # Consider adding a check or locking mechanism if necessary
            DocumentChunk.objects.filter(document=doc).delete()
            DocumentChunk.objects.bulk_create(chunks_to_create, batch_size=100) # Adjust batch_size as needed

        doc.status = KnowledgeDocument.Status.COMPLETED
        doc.processed_at = timezone.now()
        doc.error_message = None
        doc.save(update_fields=['status', 'processed_at', 'error_message'])
        logger.info(f"Successfully processed KnowledgeDocument ID: {document_id}")

    except Exception as e:
        logger.exception(f"Failed processing KnowledgeDocument ID: {document_id}", exc_info=True)
        doc.status = KnowledgeDocument.Status.FAILED
        doc.processed_at = timezone.now()
        doc.error_message = str(e)
        doc.save(update_fields=['status', 'processed_at', 'error_message']) 