import logging

from celery import shared_task

from apps.marketplace.favorites.services import process_discovery_alerts

logger = logging.getLogger(__name__)


@shared_task(name='apps.marketplace.favorites.tasks.process_discovery_alerts_task')
def process_discovery_alerts_task(limit=500):
    """
    Periodically notifies buyers about followed-shop listings and watched listing changes.
    """
    count = process_discovery_alerts(limit=limit)
    if count:
        logger.info("Celery task generated %s discovery alert(s).", count)
    return count
