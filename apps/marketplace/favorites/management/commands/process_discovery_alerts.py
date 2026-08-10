from django.core.management.base import BaseCommand

from apps.marketplace.favorites.services import process_discovery_alerts


class Command(BaseCommand):
    help = 'Notify buyers about followed-shop listings and watched listing changes.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        count = process_discovery_alerts(limit=max(1, options['limit']))
        self.stdout.write(self.style.SUCCESS(f'Created {count} discovery alert(s).'))
