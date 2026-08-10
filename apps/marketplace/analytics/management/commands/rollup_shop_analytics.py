from datetime import timedelta

from django.core.management.base import BaseCommand

from apps.marketplace.analytics.services import (
    nairobi_today,
    rollup_shop_range,
    rollup_yesterday_for_active_shops,
    shops_with_paid_activity,
)


class Command(BaseCommand):
    help = (
        'Roll up shop and listing daily analytics metrics. '
        'Default: recompute yesterday for shops with paid activity.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--backfill',
            action='store_true',
            help='Backfill the last N days (inclusive of today) for shops with paid activity.',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to backfill when --backfill is set (default: 30).',
        )

    def handle(self, *args, **options):
        if options['backfill']:
            days = max(1, options['days'])
            end = nairobi_today()
            start = end - timedelta(days=days - 1)
            shops = shops_with_paid_activity(since=start)
            shop_count = 0
            day_count = 0
            for shop in shops:
                day_count += rollup_shop_range(shop=shop, start=start, end=end)
                shop_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'Backfilled {day_count} shop-day(s) across {shop_count} shop(s) '
                    f'({start} → {end}).'
                )
            )
            return

        count = rollup_yesterday_for_active_shops()
        yesterday = nairobi_today() - timedelta(days=1)
        self.stdout.write(
            self.style.SUCCESS(f'Rolled up {count} shop(s) for {yesterday}.')
        )
