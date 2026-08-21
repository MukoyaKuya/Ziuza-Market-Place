import logging

from celery import shared_task

from apps.marketplace.notifications.delivery import deliver_pending_notifications

logger = logging.getLogger(__name__)


@shared_task(name='apps.marketplace.notifications.tasks.deliver_notifications_task')
def deliver_notifications_task(limit=500):
    """
    Periodically processes and delivers due queued email notifications.
    """
    result = deliver_pending_notifications(limit=limit)
    if result.get('sent') or result.get('failed'):
        logger.info(
            "Celery task delivered %s queued notification(s); %s failed.",
            result.get('sent', 0),
            result.get('failed', 0),
        )
    return result


@shared_task(name='apps.marketplace.notifications.tasks.trigger_async_notification_delivery')
def trigger_async_notification_delivery():
    """
    On-demand asynchronous trigger for delivering urgent queued notifications.
    """
    return deliver_pending_notifications(limit=100)
