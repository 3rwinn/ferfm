from rest_framework import viewsets
from .models import Actu
from .serializers import ActuSerializer

class ActuViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Actu.objects.all().order_by('-created_at')
    serializer_class = ActuSerializer