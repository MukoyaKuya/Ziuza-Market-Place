from django.core.management.base import BaseCommand

from apps.core.retention import purge_operational_data


class Command(BaseCommand):
    help = 'Report operational retention candidates, or purge them with --execute.'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true', help='Apply deletion/redaction instead of reporting only.')

    def handle(self, *args, **options):
        execute = options['execute']
        counts = purge_operational_data(execute=execute)
        action = 'Purged/redacted' if execute else 'Would purge/redact'
        summary = ', '.join(f'{name}={count}' for name, count in counts.items())
        self.stdout.write(self.style.SUCCESS(f'{action}: {summary}'))
