from rest_framework import serializers
from .models import Actu

class ActuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actu
        fields = ['id', 'text', 'created_at']
        read_only_fields = ['created_at'] 