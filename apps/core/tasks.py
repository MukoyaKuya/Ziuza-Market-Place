import logging

from celery import shared_task

from apps.core.retention import purge_operational_data

logger = logging.getLogger(__name__)


@shared_task(name='apps.core.tasks.purge_operational_data_task')
def purge_operational_data_task():
    counts = purge_operational_data(execute=True)
    logger.info('Operational retention completed: %s', counts)
    return counts
