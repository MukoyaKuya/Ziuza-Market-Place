from django.core.management.base import BaseCommand

from apps.marketplace.reviews.services import process_review_reminders


class Command(BaseCommand):
    help = 'Notify buyers to review purchases three days after confirmed delivery.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        count = process_review_reminders(limit=max(1, options['limit']))
        self.stdout.write(self.style.SUCCESS(f'Created {count} review reminder(s).'))
