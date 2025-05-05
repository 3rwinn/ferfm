from rest_framework import serializers

class KnowledgeQuerySerializer(serializers.Serializer):
    """Serializer for the user's question."""
    question = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="The question to ask the knowledge base."
    )
    # Optional: Add filters like document IDs, date ranges, etc.
    # document_ids = serializers.ListField(
    #     child=serializers.UUIDField(),
    #     required=False,
    #     help_text="Optional list of specific document IDs to query."
    # )

class KnowledgeAnswerSerializer(serializers.Serializer):
    """Serializer for the generated answer."""
    answer = serializers.CharField(
        read_only=True,
        help_text="The answer generated based on the provided documents."
    )
    # Optional: Include source chunks or metadata for reference
    # source_chunks = serializers.ListField(
    #     child=serializers.CharField(),
    #     read_only=True,
    #     required=False,
    #     help_text="Text content of the source chunks used for the answer."
    # ) 