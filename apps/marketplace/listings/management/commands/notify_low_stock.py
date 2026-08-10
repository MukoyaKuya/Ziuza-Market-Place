from django.core.management.base import BaseCommand

from apps.marketplace.listings.models import Inventory, ListingStatus
from apps.marketplace.notifications.services import notify


class Command(BaseCommand):
    help = 'Notify sellers once when active listing inventory reaches its low-stock threshold.'

    def handle(self, *args, **options):
        sent = 0
        rows = Inventory.objects.select_related('listing__shop__owner').filter(
            listing__status=ListingStatus.ACTIVE,
            low_stock_alert_sent=False,
        )
        for inventory in rows:
            if inventory.available_to_sell > inventory.low_stock_threshold:
                continue
            listing = inventory.listing
            notify(
                recipient=listing.shop.owner,
                type='low_stock',
                title=f'Low stock: {listing.title}',
                body=f'{inventory.available_to_sell} available; alert threshold is {inventory.low_stock_threshold}.',
                target_url=f'/seller/listings/{listing.id}/',
            )
            inventory.low_stock_alert_sent = True
            inventory.save(update_fields=['low_stock_alert_sent', 'updated_at'])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} low-stock alert(s).'))
