import logging
from datetime import timedelta
from celery import shared_task

from apps.marketplace.analytics.services import (
    nairobi_today,
    rollup_shop_range,
    rollup_yesterday_for_active_shops,
    shops_with_paid_activity,
)

logger = logging.getLogger(__name__)


@shared_task(name='apps.marketplace.analytics.tasks.rollup_shop_analytics_task')
def rollup_shop_analytics_task(days=1, backfill=False):
    """
    Periodically rolls up shop and listing daily analytics metrics.
    """
    if backfill:
        days = max(1, days)
        end = nairobi_today()
        start = end - timedelta(days=days - 1)
        shops = shops_with_paid_activity(since=start)
        shop_count = 0
        day_count = 0
        for shop in shops:
            day_count += rollup_shop_range(shop=shop, start=start, end=end)
            shop_count += 1
        logger.info(
            "Celery backfilled %s shop-day(s) across %s shop(s) (%s -> %s).",
            day_count,
            shop_count,
            start,
            end,
        )
        return {'shop_count': shop_count, 'day_count': day_count}

    count = rollup_yesterday_for_active_shops()
    yesterday = nairobi_today() - timedelta(days=1)
    logger.info("Celery rolled up %s shop(s) for %s.", count, yesterday)
    return {'shop_count': count, 'date': str(yesterday)}
