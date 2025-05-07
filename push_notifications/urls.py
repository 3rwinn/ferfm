from django.urls import path
from .views import RegisterExpoPushTokenView

app_name = 'push_notifications'

urlpatterns = [
    path('register-token/', RegisterExpoPushTokenView.as_view(), name='register_expo_token'),
] 