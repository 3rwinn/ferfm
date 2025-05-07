from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import Actu
from .serializers import ActuSerializer

class ActuViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Actu.objects.all().order_by('-created_at')
    permission_classes = [AllowAny]
    serializer_class = ActuSerializer
