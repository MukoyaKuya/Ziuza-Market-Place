import pytest
from django.conf import settings

from config.celery import app as celery_app, debug_task
from apps.marketplace.orders.tasks import expire_order_reservations_task
from apps.marketplace.notifications.tasks import (
    deliver_notifications_task,
    trigger_async_notification_delivery,
)
from apps.marketplace.search.tasks import process_saved_search_alerts_task
from apps.marketplace.favorites.tasks import process_discovery_alerts_task
from apps.marketplace.listings.tasks import notify_low_stock_task
from apps.marketplace.reviews.tasks import process_review_reminders_task
from apps.marketplace.analytics.tasks import rollup_shop_analytics_task


def test_celery_app_is_configured():
    assert celery_app.main == 'ziuza'
    assert settings.CELERY_TASK_ALWAYS_EAGER is True


def test_celery_beat_schedule_is_registered():
    schedule = settings.CELERY_BEAT_SCHEDULE
    expected_tasks = {
        'expire-order-reservations-every-minute': 'apps.marketplace.orders.tasks.expire_order_reservations_task',
        'deliver-notifications-every-minute': 'apps.marketplace.notifications.tasks.deliver_notifications_task',
        'process-saved-search-alerts-every-15-mins': 'apps.marketplace.search.tasks.process_saved_search_alerts_task',
        'process-discovery-alerts-every-15-mins': 'apps.marketplace.favorites.tasks.process_discovery_alerts_task',
        'notify-low-stock-daily': 'apps.marketplace.listings.tasks.notify_low_stock_task',
        'process-review-reminders-daily': 'apps.marketplace.reviews.tasks.process_review_reminders_task',
        'rollup-shop-analytics-daily': 'apps.marketplace.analytics.tasks.rollup_shop_analytics_task',
    }
    for schedule_name, task_path in expected_tasks.items():
        assert schedule_name in schedule
        assert schedule[schedule_name]['task'] == task_path


@pytest.mark.django_db
def test_expire_order_reservations_task_runs_eagerly():
    result = expire_order_reservations_task.delay()
    assert result.successful()
    assert isinstance(result.result, int)


@pytest.mark.django_db
def test_deliver_notifications_tasks_run_eagerly():
    res1 = deliver_notifications_task.delay(limit=10)
    assert res1.successful()
    assert 'sent' in res1.result
    assert 'failed' in res1.result

    res2 = trigger_async_notification_delivery.delay()
    assert res2.successful()
    assert 'sent' in res2.result


@pytest.mark.django_db
def test_search_and_discovery_tasks_run_eagerly():
    search_res = process_saved_search_alerts_task.delay(limit=10)
    assert search_res.successful()
    assert isinstance(search_res.result, int)

    discovery_res = process_discovery_alerts_task.delay(limit=10)
    assert discovery_res.successful()
    assert isinstance(discovery_res.result, int)


@pytest.mark.django_db
def test_listings_and_reviews_tasks_run_eagerly():
    stock_res = notify_low_stock_task.delay()
    assert stock_res.successful()
    assert isinstance(stock_res.result, int)

    review_res = process_review_reminders_task.delay(limit=10)
    assert review_res.successful()
    assert isinstance(review_res.result, int)


@pytest.mark.django_db
def test_analytics_task_runs_eagerly():
    analytics_res = rollup_shop_analytics_task.delay()
    assert analytics_res.successful()
    assert 'shop_count' in analytics_res.result

    backfill_res = rollup_shop_analytics_task.delay(days=3, backfill=True)
    assert backfill_res.successful()
    assert 'shop_count' in backfill_res.result
    assert 'day_count' in backfill_res.result


def test_debug_task_runs_eagerly():
    res = debug_task.delay()
    assert res.successful()
