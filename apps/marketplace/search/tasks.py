import logging

from celery import shared_task

from apps.marketplace.search.saved import process_saved_search_alerts

logger = logging.getLogger(__name__)


@shared_task(name='apps.marketplace.search.tasks.process_saved_search_alerts_task')
def process_saved_search_alerts_task(limit=500):
    """
    Periodically processes saved searches and creates in-app notifications for matching new listings.
    """
    count = process_saved_search_alerts(limit=limit)
    if count:
        logger.info("Celery task generated alerts for %s saved search(es).", count)
    return count
