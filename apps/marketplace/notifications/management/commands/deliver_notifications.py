from django.core.management.base import BaseCommand

from apps.marketplace.notifications.delivery import deliver_pending_notifications


class Command(BaseCommand):
    help = 'Deliver due queued notification emails and retry temporary failures.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        result = deliver_pending_notifications(limit=max(1, options['limit']))
        self.stdout.write(self.style.SUCCESS(
            f"Delivered {result['sent']} queued notification(s); {result['failed']} failed and will retry when eligible."
        ))
