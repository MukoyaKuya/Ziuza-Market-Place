from django.core.management.base import BaseCommand

from apps.marketplace.orders.services import expire_stale_orders


class Command(BaseCommand):
    help = 'Release inventory reserved by expired, unpaid orders.'

    def handle(self, *args, **options):
        count = expire_stale_orders()
        self.stdout.write(self.style.SUCCESS(f'Released {count} expired order reservation(s).'))
