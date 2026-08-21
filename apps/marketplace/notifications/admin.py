from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.notifications.models import Notification, NotificationDelivery, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('title', 'recipient', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read')
    search_fields = ('title', 'body', 'recipient__email')
    raw_id_fields = ('recipient',)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(ModelAdmin):
    list_display = ('user', 'email_enabled', 'digest_frequency', 'updated_at')
    list_filter = ('email_enabled', 'digest_frequency')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(ModelAdmin):
    list_display = ('notification', 'recipient', 'mode', 'status', 'attempts', 'available_at', 'sent_at')
    list_filter = ('channel', 'mode', 'status')
    search_fields = ('recipient__email', 'notification__title', 'last_error')
    raw_id_fields = ('notification', 'recipient')
    readonly_fields = (
        'notification', 'recipient', 'channel', 'mode', 'status', 'available_at',
        'attempts', 'last_error', 'sent_at', 'created_at', 'updated_at',
    )

    def has_add_permission(self, request):
        return False
