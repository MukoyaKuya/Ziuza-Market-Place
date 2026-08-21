import logging

from celery import shared_task

from apps.marketplace.cart.services import purge_inactive_anonymous_carts

logger = logging.getLogger(__name__)


@shared_task(name='apps.marketplace.cart.tasks.purge_inactive_anonymous_carts_task')
def purge_inactive_anonymous_carts_task(days: int = 30):
    """Celery periodic task to purge stale anonymous carts."""
    deleted_count = purge_inactive_anonymous_carts(days=days)
    logger.info('Purged %d inactive anonymous carts older than %d days', deleted_count, days)
    return deleted_count
