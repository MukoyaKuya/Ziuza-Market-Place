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


@pytest.mark.django_db
def test_readiness_health_endpoint(client):
    url = reverse('health:ready')
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ready'
    assert data['database'] == 'ok'


@pytest.mark.django_db
def test_home_page_renders(client):
    url = reverse('core:home')
    response = client.get(url)
    assert response.status_code == 200
    assert b'ZIUZA' in response.content
    assert b'Made in' in response.content
