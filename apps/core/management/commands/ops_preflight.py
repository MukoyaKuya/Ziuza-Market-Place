from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Run read-only deployment checks for database, migrations, assets, and optional Celery workers.'

    def add_arguments(self, parser):
        parser.add_argument('--require-celery', action='store_true')

    def handle(self, *args, **options):
        failures = []
        non_delivery_email_backends = {
            'django.core.mail.backends.console.EmailBackend',
            'django.core.mail.backends.dummy.EmailBackend',
            'django.core.mail.backends.filebased.EmailBackend',
            'django.core.mail.backends.locmem.EmailBackend',
        }
        if (
            getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', True)
            and settings.EMAIL_BACKEND in non_delivery_email_backends
        ):
            failures.append('email verification requires a delivery-capable EMAIL_BACKEND')

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                if cursor.fetchone() != (1,):
                    failures.append('database ping returned an unexpected result')
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if pending:
                failures.append(f'{len(pending)} database migration(s) are pending')
        except Exception as exc:
            failures.append(f'database preflight failed: {type(exc).__name__}')

        css_path = settings.BASE_DIR / 'static' / 'css' / 'styles.css'
        if not css_path.is_file() or css_path.stat().st_size == 0:
            failures.append('compiled static/css/styles.css is missing or empty')

        if options['require_celery']:
            try:
                from config.celery import app as celery_app

                inspector = celery_app.control.inspect(timeout=2.0)
                if not inspector or not inspector.ping():
                    failures.append('no Celery worker responded')
            except Exception as exc:
                failures.append(f'Celery preflight failed: {type(exc).__name__}')

        if failures:
            raise CommandError('; '.join(failures))
        self.stdout.write(self.style.SUCCESS('Operational preflight passed.'))
