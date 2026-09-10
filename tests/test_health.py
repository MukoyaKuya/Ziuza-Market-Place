from unittest.mock import patch

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_liveness_health_endpoint(client):
    url = reverse('health:live')
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'live'
    assert data['service'] == 'ziuza-marketplace'
    assert response.headers.get('X-Request-ID')


@pytest.mark.django_db
def test_request_id_header_echoed(client):
    url = reverse('health:live')
    custom_id = 'abc123deadbeef'
    response = client.get(url, HTTP_X_REQUEST_ID=custom_id)
    assert response.status_code == 200
    assert response.headers.get('X-Request-ID') == custom_id


@pytest.mark.django_db
def test_readiness_health_endpoint(client):
    url = reverse('health:ready')
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ready'
    assert data['database'] == 'ok'


@pytest.mark.django_db
def test_readiness_health_with_celery_param(client):
    url = f"{reverse('health:ready')}?check_celery=1"
    with patch('config.celery.app.control.inspect') as inspect:
        inspect.return_value.ping.return_value = {'worker-1': {'ok': 'pong'}}
        response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ready'
    assert 'celery' in data


@pytest.mark.django_db
def test_readiness_fails_when_required_celery_worker_is_unavailable(client):
    url = f"{reverse('health:ready')}?check_celery=1"
    with patch('config.celery.app.control.inspect') as inspect:
        inspect.return_value.ping.return_value = None
        response = client.get(url)

    assert response.status_code == 503
    assert response.json()['celery'] == 'no_workers'


@pytest.mark.django_db
def test_readiness_does_not_disclose_database_errors(client):
    with patch('apps.core.views.health.connection.cursor', side_effect=RuntimeError('secret-db-host')):
        response = client.get(reverse('health:ready'))

    assert response.status_code == 503
    assert response.json()['database'] == 'failed'
    assert 'error' not in response.json()
    assert b'secret-db-host' not in response.content


@pytest.mark.django_db
def test_home_page_renders(client):
    url = reverse('core:home')
    response = client.get(url)
    assert response.status_code == 200
    assert b'ZIUZA' in response.content
    assert b'Made in' in response.content
