import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_custom_404_page(client):
    response = client.get('/this-route-does-not-exist/')
    assert response.status_code == 404
    assert b'Page Not Found' in response.content
    assert b'Return to Marketplace Home' in response.content


@pytest.mark.django_db
def test_home_still_resolves_after_error_handlers(client):
    response = client.get(reverse('core:home'))
    assert response.status_code == 200
