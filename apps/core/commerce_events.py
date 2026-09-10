import json
import logging

from django.utils import timezone

logger = logging.getLogger('commerce')

SENSITIVE_FIELDS = frozenset({'address', 'email', 'payload', 'phone', 'secret', 'token'})


def emit_commerce_event(event: str, **fields) -> None:
    if SENSITIVE_FIELDS.intersection(fields):
        raise ValueError('Commerce events cannot include sensitive fields.')
    record = {
        'event': event,
        'version': 1,
        'timestamp': timezone.now().isoformat(),
        **fields,
    }
    logger.info(json.dumps(record, sort_keys=True, default=str))
