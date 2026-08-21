from django.core.management.base import BaseCommand
from apps.marketplace.cart.services import purge_inactive_anonymous_carts


class Command(BaseCommand):
    help = 'Purge stale anonymous carts older than the specified number of days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Retention window in days (default: 30)',
        )

    def handle(self, *args, **options):
        days = options['days']
        deleted_count = purge_inactive_anonymous_carts(days=days)
        self.stdout.write(
            self.style.SUCCESS(f'Successfully purged {deleted_count} inactive anonymous cart(s) older than {days} day(s).')
        )
