def unread_notifications(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'unread_notification_count': 0}
    try:
        from apps.marketplace.notifications.models import Notification

        return {
            'unread_notification_count': Notification.objects.filter(
                recipient=request.user,
                is_read=False,
            ).count()
        }
    except Exception:
        return {'unread_notification_count': 0}
