from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ActuViewSet

app_name = 'actus'

router = DefaultRouter()
router.register(r'actus', ActuViewSet, basename='actu')

urlpatterns = [
    path('', include(router.urls)),
] 