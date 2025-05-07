from django.contrib import admin, messages
from .models import ExpoPushToken, Notification, NotificationDelivery
from .tasks import queue_notification_for_sending # Import the task queuing function
from django.utils import timezone

@admin.register(ExpoPushToken)
class ExpoPushTokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('token',)
    actions = ['mark_as_active', 'mark_as_inactive']

    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} tokens marked as active.", messages.SUCCESS)
    mark_as_active.short_description = "Mark selected tokens as active"

    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} tokens marked as inactive.", messages.SUCCESS)
    mark_as_inactive.short_description = "Mark selected tokens as inactive"

class NotificationDeliveryInline(admin.TabularInline):
    model = NotificationDelivery
    extra = 0
    readonly_fields = ('expo_push_token', 'push_ticket_id', 'status', 'receipt_status_text', 'receipt_checked_at', 'receipt_details', 'created_at', 'updated_at')
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'creator', 'scheduled_at', 'sent_at', 'created_at')
    list_filter = ('status', 'creator', 'scheduled_at')
    search_fields = ('title', 'body')
    inlines = [NotificationDeliveryInline]
    actions = ['process_selected_notifications']
    readonly_fields = ('sent_at', 'status') # status is now managed by the queueing logic primarily

    def process_selected_notifications(self, request, queryset):
        processed_count = 0
        skipped_count = 0
        for notification in queryset:
            if notification.status == 'draft':
                # If scheduled_at is set and in the future, it will be scheduled.
                # Otherwise, it will be queued for immediate sending.
                queue_notification_for_sending(notification.id)
                processed_count += 1
            else:
                skipped_count += 1
        
        if processed_count > 0:
            self.message_user(request, f"{processed_count} notifications have been queued or scheduled.", messages.SUCCESS)
        if skipped_count > 0:
            self.message_user(request, f"{skipped_count} notifications were skipped (not in 'draft' status).", messages.WARNING)
    process_selected_notifications.short_description = "Queue/Schedule selected draft notifications"

@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ('notification', 'get_token_short', 'status', 'push_ticket_id', 'receipt_status_text', 'receipt_checked_at', 'updated_at')
    list_filter = ('status', 'receipt_status_text', 'receipt_checked_at')
    search_fields = ('push_ticket_id', 'expo_push_token__token', 'notification__title')
    readonly_fields = ('notification', 'expo_push_token', 'push_ticket_id', 'receipt_details', 'created_at', 'updated_at', 'status', 'receipt_status_text', 'receipt_checked_at')

    def get_token_short(self, obj):
        if obj.expo_push_token:
            return str(obj.expo_push_token)[:30] + "..."
        return None
    get_token_short.short_description = 'Expo Token (Shortened)'

    def has_add_permission(self, request):
        return False

    # def has_change_permission(self, request, obj=None):
    #     return False # Usually not changed manually

    # def has_delete_permission(self, request, obj=None):
    #     return False # Usually not deleted manually
