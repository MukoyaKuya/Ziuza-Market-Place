import logging

from django.db import connection
from django.http import JsonResponse
from django.views import View

logger = logging.getLogger(__name__)


class LivenessHealthView(View):
    """Basic liveness probe endpoint returning 200 OK."""

    def get(self, request, *args, **kwargs):
        return JsonResponse({'status': 'live', 'service': 'ziuza-marketplace'}, status=200)


class ReadinessHealthView(View):
    """Readiness probe endpoint checking database connectivity and background workers."""

    def get(self, request, *args, **kwargs):
        db_healthy = False
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1;')
                row = cursor.fetchone()
                if row and row[0] == 1:
                    db_healthy = True
        except Exception:
            logger.exception('Readiness check failed database ping')

        celery_status = 'not_checked'
        if request.GET.get('check_celery') == '1':
            try:
                from config.celery import app as celery_app
                inspector = celery_app.control.inspect(timeout=1.0)
                ping = inspector.ping() if inspector else None
                celery_status = 'ok' if ping else 'no_workers'
            except Exception as exc:
                logger.warning("Celery health check error: %s", exc)
                celery_status = 'unreachable'

        ready = db_healthy and celery_status in {'not_checked', 'ok'}
        if ready:
            payload = {
                'status': 'ready',
                'database': 'ok',
                'service': 'ziuza-marketplace',
            }
            if celery_status != 'not_checked':
                payload['celery'] = celery_status
            return JsonResponse(payload, status=200)

        payload = {
            'status': 'unready',
            'database': 'ok' if db_healthy else 'failed',
            'service': 'ziuza-marketplace',
        }
        if celery_status != 'not_checked':
            payload['celery'] = celery_status
        return JsonResponse(payload, status=503)
