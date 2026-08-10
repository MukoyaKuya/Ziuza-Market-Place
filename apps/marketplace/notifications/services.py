# Re-export for `from apps.marketplace.notifications.services import notify`
from apps.marketplace.notifications.models import mark_notification_read, notify

__all__ = ['notify', 'mark_notification_read']
