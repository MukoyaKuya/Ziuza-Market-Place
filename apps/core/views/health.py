from django.http import JsonResponse
from django.views import View
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class LivenessHealthView(View):
    """Basic liveness probe endpoint returning 200 OK."""

    def get(self, request, *args, **kwargs):
        return JsonResponse({'status': 'live', 'service': 'ziuza-marketplace'}, status=200)


class ReadinessHealthView(View):
    """Readiness probe endpoint checking database connectivity."""

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

        if db_healthy:
            return JsonResponse({
                'status': 'ready',
                'database': 'ok',
                'service': 'ziuza-marketplace'
            }, status=200)
        
        return JsonResponse({
            'status': 'unready',
            'database': 'failed',
            'error': error_msg,
            'service': 'ziuza-marketplace'
        }, status=503)
