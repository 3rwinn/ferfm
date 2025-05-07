from django.apps import AppConfig


class PushNotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "push_notifications"

    def ready(self):
        try:
            import push_notifications.signals
        except ImportError:
            pass
        # You can also print a message here for debugging if you want to confirm signals are loaded
        # print("Push notification signals loaded.")
