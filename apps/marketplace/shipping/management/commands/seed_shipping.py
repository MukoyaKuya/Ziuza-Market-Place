from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.marketplace.shipping.models import ShippingMethod


class Command(BaseCommand):
    help = 'Seed shipping methods'

    def handle(self, *args, **options):
        ShippingMethod.objects.get_or_create(
            code='standard',
            defaults={'name': 'Standard delivery', 'base_fee': Decimal('300.00'), 'estimated_days_min': 2, 'estimated_days_max': 5},
        )
        ShippingMethod.objects.get_or_create(
            code='pickup',
            defaults={'name': 'Local pickup', 'base_fee': Decimal('0.00'), 'estimated_days_min': 1, 'estimated_days_max': 2, 'is_pickup': True},
        )
        self.stdout.write(self.style.SUCCESS('Shipping methods seeded.'))
