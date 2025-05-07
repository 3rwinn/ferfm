from rest_framework import serializers
from .models import ExpoPushToken

class ExpoPushTokenSerializer(serializers.ModelSerializer):
    token = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = ExpoPushToken
        fields = ['id', 'token', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at']

    def validate_token(self, value):
        # Basic validation, Expo tokens often start with ExponentPushToken[...]
        # You might want to add more robust validation if needed, e.g., regex
        if not value or not isinstance(value, str):
            raise serializers.ValidationError("Expo token must be a non-empty string.")
        # Example: Simple check for prefix, can be made more robust
        # if not value.startswith("ExponentPushToken[") and not value.startswith("ExpoPushToken["):
        #     raise serializers.ValidationError("Invalid Expo token format.")
        return value 