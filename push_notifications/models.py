from django.db import models
from django.conf import settings


class ExpoPushToken(models.Model):
    token = models.CharField(max_length=255, unique=True)  # Expo tokens can be long
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.token[:50] + ("..." if len(self.token) > 50 else "")


class Notification(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("queued", "Queued"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),  # All messages sent to Expo, awaiting receipts
        (
            "completed_with_errors",
            "Completed (with errors)",
        ),  # Some receipts were errors
        ("completed_success", "Completed (all success)"),  # All receipts were 'ok'
        ("failed", "Failed"),  # Failed to even send to Expo for some major reason
    ]

    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(null=True, blank=True)

    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True
    )

    # Assuming you have a custom user model, otherwise use settings.AUTH_USER_MODEL
    # If no admin/user is creating it (e.g. system generated for Actu), this can be null
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notifications",
    )

    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(
        null=True, blank=True
    )  # When the sending process began

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class NotificationDelivery(models.Model):
    DELIVERY_STATUS_CHOICES = [
        ("pending_send", "Pending Send"),  # Task created, not yet sent to Expo
        ("sent_to_expo", "Sent to Expo"),  # Successfully sent to Expo, ticket received
        (
            "expo_error",
            "Expo Send Error",
        ),  # Error when trying to send to Expo (no ticket)
        (
            "receipt_pending_check",
            "Receipt Pending Check",
        ),  # Ticket received, awaiting receipt check
        ("receipt_ok", "Receipt OK"),  # Expo confirmed delivery
        (
            "receipt_error",
            "Receipt Error",
        ),  # Expo reported an error (e.g., DeviceNotRegistered)
    ]

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    expo_push_token = models.ForeignKey(
        ExpoPushToken, on_delete=models.CASCADE, related_name="deliveries"
    )

    # Expo push ticket ID, received after sending a message
    push_ticket_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )

    status = models.CharField(
        max_length=30,
        choices=DELIVERY_STATUS_CHOICES,
        default="pending_send",
        db_index=True,
    )

    # Timestamp when the receipt was checked
    receipt_checked_at = models.DateTimeField(null=True, blank=True)

    # Status from the Expo receipt ('ok' or 'error')
    receipt_status_text = models.CharField(
        max_length=50, null=True, blank=True
    )  # 'ok', 'error', etc.

    # Full details from the Expo receipt, especially if there's an error
    receipt_details = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "notification",
            "expo_push_token",
        )  # Ensure one delivery record per token per notification
        ordering = ["-created_at"]

    def __str__(self):
        return f"To: {self.expo_push_token.token[:20]}... - Status: {self.get_status_display()}"
