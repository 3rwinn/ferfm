from django.shortcuts import render
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# Or AllowAny for testing
from rest_framework.permissions import IsAuthenticated, AllowAny

from pgvector.django import CosineDistance
from sentence_transformers import SentenceTransformer

# Local imports
from .models import DocumentChunk, KnowledgeDocument
from .serializers import KnowledgeQuerySerializer, KnowledgeAnswerSerializer
from services.gemini_service import generate_answer
# Use the same model as the processing task
from .tasks import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

# --- Constants ---
# Number of relevant chunks to retrieve for context
TOP_K = 5

# --- Load Model Globally (for efficiency within the API worker process) ---
# Ensure this matches the model used in tasks.py
# Consider error handling if the model fails to load
try:
    logger.info(f"Loading embedding model for API: {EMBEDDING_MODEL_NAME}")
    # Force CPU if needed: device='cpu'
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logger.info("Embedding model loaded successfully for API.")
except Exception as e:
    logger.error(
        f"Failed to load embedding model {EMBEDDING_MODEL_NAME}: {e}", exc_info=True)
    # Depending on desired behavior, you might raise an error or disable the endpoint
    embedding_model = None


class QueryKnowledgeView(APIView):
    """
    API endpoint to ask questions based on the indexed knowledge documents.
    Requires POST request with JSON body: {"question": "Your question here?"}
    """
    # permission_classes = [IsAuthenticated] # Adjust as needed (e.g., AllowAny)
    permission_classes = [AllowAny]  # Adjust as needed (e.g., AllowAny)

    def post(self, request, *args, **kwargs):
        if not embedding_model:
            return Response(
                {"error": "Embedding model is not available. Cannot process query."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        serializer = KnowledgeQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        question = serializer.validated_data['question']
        logger.info(f"Received knowledge query: '{question[:100]}...'")

        try:
            # 1. Generate embedding for the question
            logger.debug("Generating embedding for the query...")
            question_embedding = embedding_model.encode(question)

            # 2. Find relevant document chunks via vector similarity search
            # Only search chunks from documents that have been successfully processed
            logger.debug(f"Searching for top {TOP_K} relevant chunks...")
            relevant_chunks = DocumentChunk.objects.filter(
                document__status=KnowledgeDocument.Status.COMPLETED
            ).order_by(
                CosineDistance('embedding', question_embedding)
            )[:TOP_K]

            if not relevant_chunks:
                logger.warning(
                    "No relevant document chunks found for the query.")
                # Consider a specific response or letting Gemini handle it
                # return Response({"answer": "I could not find relevant information in the knowledge base to answer your question."}, status=status.HTTP_200_OK)
                knowledge_snippets = []  # Pass empty list to Gemini
            else:
                knowledge_snippets = [
                    chunk.text_content for chunk in relevant_chunks]
                logger.info(
                    f"Retrieved {len(knowledge_snippets)} snippets for context.")
                # for i, snippet in enumerate(knowledge_snippets):
                #     logger.debug(f"Snippet {i+1}: {snippet[:100]}...")

            # 3. Generate answer using Gemini with retrieved context
            logger.debug("Calling Gemini service to generate answer...")
            answer_text = generate_answer(
                user_question=question,
                knowledge_snippets=knowledge_snippets
            )

            # 4. Serialize and return response
            # response_serializer = KnowledgeAnswerSerializer(
            #     data={'answer': answer_text})
            # response_serializer.is_valid(raise_exception=True) # Check validation and raise error if invalid
            # return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response({"answer": answer_text}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(
                "Error occurred during knowledge query processing.", exc_info=True)
            return Response(
                {"error": "An internal error occurred while processing your query.",
                    "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
