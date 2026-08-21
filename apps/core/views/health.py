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
        error_msg = None
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1;')
                row = cursor.fetchone()
                if row and row[0] == 1:
                    db_healthy = True
        except Exception as e:
            logger.error("Readiness check failed database ping: %s", e)
            error_msg = str(e)

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

        if db_healthy:
            payload = {
                'status': 'ready',
                'database': 'ok',
                'service': 'ziuza-marketplace',
            }
            if celery_status != 'not_checked':
                payload['celery'] = celery_status
            return JsonResponse(payload, status=200)

        return JsonResponse({
            'status': 'unready',
            'database': 'failed',
            'error': error_msg,
            'service': 'ziuza-marketplace',
        }, status=503)

