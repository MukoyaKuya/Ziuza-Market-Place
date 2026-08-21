import logging

from celery import shared_task

from apps.marketplace.orders.services import expire_stale_orders

logger = logging.getLogger(__name__)


@shared_task(name='apps.marketplace.orders.tasks.expire_order_reservations_task')
def expire_order_reservations_task():
    """
    Periodically releases inventory reserved by expired, unpaid orders.
    """
    count = expire_stale_orders()
    if count:
        logger.info("Celery task released %s expired order reservation(s).", count)
    return count
