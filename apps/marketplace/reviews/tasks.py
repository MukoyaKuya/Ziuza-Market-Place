import logging

from celery import shared_task

from apps.marketplace.reviews.services import process_review_reminders

logger = logging.getLogger(__name__)


@shared_task(name='apps.marketplace.reviews.tasks.process_review_reminders_task')
def process_review_reminders_task(limit=500):
    """
    Periodically notifies buyers to review purchases three days after confirmed delivery.
    """
    count = process_review_reminders(limit=limit)
    if count:
        logger.info("Celery task created %s review reminder(s).", count)
    return count
