from django.shortcuts import render
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from .models import ExpoPushToken
from .serializers import ExpoPushTokenSerializer
from django.utils import timezone

# Create your views here.

class RegisterExpoPushTokenView(generics.CreateAPIView):
    serializer_class = ExpoPushTokenSerializer
    permission_classes = [permissions.AllowAny] # As per PRD, no auth needed

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_str = serializer.validated_data['token']

        # Check if token already exists
        token, created = ExpoPushToken.objects.update_or_create(
            token=token_str,
            defaults={'is_active': True, 'updated_at': timezone.now()}
        )

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        message = "Token registered successfully." if created else "Token updated successfully."
        
        # Return the serialized token data (or just a success message)
        # Re-serializing the instance to include all fields for the response
        response_serializer = self.get_serializer(token)
        return Response({"success": True, "message": message, "data": response_serializer.data}, status=response_status)

# Placeholder for future views if needed
