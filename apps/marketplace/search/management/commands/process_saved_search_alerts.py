from django.core.management.base import BaseCommand

from apps.marketplace.search.saved import process_saved_search_alerts


class Command(BaseCommand):
    help = 'Create in-app notifications for new listings matching saved searches.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        count = process_saved_search_alerts(limit=max(1, options['limit']))
        self.stdout.write(self.style.SUCCESS(f'Created alerts for {count} saved search(es).'))
