import json

from django.http import HttpResponse


def with_toast(response: HttpResponse, *, message: str, type: str = 'info') -> HttpResponse:
    """Attach an HX-Trigger so Alpine toast listeners can show feedback."""
    payload = {'toast': {'message': message, 'type': type}}
    existing = response.headers.get('HX-Trigger')
    if existing:
        try:
            data = json.loads(existing)
            if isinstance(data, dict):
                data.update(payload)
                payload = data
        except json.JSONDecodeError:
            pass
    response['HX-Trigger'] = json.dumps(payload)
    return response
