import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.locations import get_counties, get_sub_counties, get_wards
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.shops.models import LocalDeliveryScope, Shop, ShopVerificationStatus
from apps.marketplace.shops.services import create_shop, update_shop_settings

User = get_user_model()


@pytest.fixture
def seller_user(db):
    return User.objects.create_user(
        email='local_seller@ziuza.test',
        password='password123',
        first_name='Amina',
        last_name='Karanja',
    )


@pytest.fixture
def local_shop(db, seller_user):
    return create_shop(
        actor=seller_user,
        name='Nairobi Pottery Works',
        description='Fine pottery and handcrafted ceramics in Westlands.',
        county='Nairobi',
        sub_county='Westlands',
        ward='Parklands/Highridge',
        village='Parklands Road',
        location_text='Opposite Diamond Plaza',
        is_local_seller=True,
        local_delivery_scope=LocalDeliveryScope.WARD,
        local_pickup_available=True,
        local_pickup_instructions='Collect at front counter from 9am to 6pm.',
    )


@pytest.fixture
def mombasa_seller(db):
    user = User.objects.create_user(
        email='mombasa_seller@ziuza.test',
        password='password123',
        first_name='Ali',
        last_name='Hassan',
    )
    return create_shop(
        actor=user,
        name='Swahili Coast Carvings',
        description='Authentic wood carvings from Nyali.',
        county='Mombasa',
        sub_county='Nyali',
        ward='Frere Town',
        location_text='Links Road',
        is_local_seller=True,
        local_delivery_scope=LocalDeliveryScope.COUNTY,
        local_pickup_available=False,
    )


@pytest.mark.django_db
def test_location_helpers():
    counties = get_counties()
    assert 'Nairobi' in counties
    assert 'Mombasa' in counties
    assert len(counties) >= 47

    nairobi_subs = get_sub_counties('Nairobi')
    assert 'Westlands' in nairobi_subs
    assert 'Kibra' in nairobi_subs

    westlands_wards = get_wards('Westlands')
    assert 'Parklands/Highridge' in westlands_wards
    assert 'Kitisuru' in westlands_wards


@pytest.mark.django_db
def test_location_options_endpoints(client):
    # Sub-counties endpoint
    url_sub = reverse('shops:sub_counties_options')
    response_sub = client.get(f'{url_sub}?county=Nairobi&selected=Westlands')
    assert response_sub.status_code == 200
    content_sub = response_sub.content.decode()
    assert '<option value="">All Sub-Counties</option>' in content_sub
    assert '<option value="Westlands" selected>Westlands</option>' in content_sub

    # Wards endpoint
    url_ward = reverse('shops:wards_options')
    response_ward = client.get(f'{url_ward}?sub_county=Westlands&selected=Parklands/Highridge')
    assert response_ward.status_code == 200
    content_ward = response_ward.content.decode()
    assert '<option value="">All Wards / Areas</option>' in content_ward
    assert '<option value="Parklands/Highridge" selected>Parklands/Highridge</option>' in content_ward


@pytest.mark.django_db
def test_local_index_renders_and_filters(client, local_shop, mombasa_seller):
    url = reverse('shops:local')
    response = client.get(url)
    assert response.status_code == 200
    assert 'Nairobi Pottery Works' in response.content.decode()
    assert 'Swahili Coast Carvings' in response.content.decode()

    # Filter by county = Nairobi
    response_nairobi = client.get(f'{url}?county=Nairobi')
    assert response_nairobi.status_code == 200
    content_nairobi = response_nairobi.content.decode()
    assert 'Nairobi Pottery Works' in content_nairobi
    assert 'Swahili Coast Carvings' not in content_nairobi

    # Filter by sub-county = Westlands
    response_westlands = client.get(f'{url}?county=Nairobi&sub_county=Westlands')
    assert response_westlands.status_code == 200
    assert 'Nairobi Pottery Works' in response_westlands.content.decode()

    # Filter by ward = Parklands/Highridge
    response_ward = client.get(f'{url}?county=Nairobi&sub_county=Westlands&ward=Parklands/Highridge')
    assert response_ward.status_code == 200
    assert 'Nairobi Pottery Works' in response_ward.content.decode()

    # Filter by ward with no shops
    response_empty_ward = client.get(f'{url}?county=Nairobi&sub_county=Westlands&ward=Kitisuru')
    assert response_empty_ward.status_code == 200
    assert 'No active sellers found' in response_empty_ward.content.decode()

    # Filter by local pickup only
    response_pickup = client.get(f'{url}?pickup=1')
    assert response_pickup.status_code == 200
    content_pickup = response_pickup.content.decode()
    assert 'Nairobi Pottery Works' in content_pickup
    assert 'Swahili Coast Carvings' not in content_pickup


@pytest.mark.django_db
def test_local_index_htmx_partial(client, local_shop):
    url = reverse('shops:local')
    response = client.get(f'{url}?county=Nairobi', HTTP_HX_REQUEST='true')
    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="local-results-container"' in content
    assert 'Nairobi Pottery Works' in content


@pytest.mark.django_db
def test_seller_onboarding_with_local_fields(client):
    user = User.objects.create_user(
        email='new_local_artisan@ziuza.test',
        password='password123',
        first_name='Grace',
        last_name='Mutua',
    )
    client.force_login(user)

    url = reverse('shops:onboarding')
    response = client.post(url, {
        'name': 'Machakos Woodcrafts',
        'description': 'Carvings and handmade bowls.',
        'county': 'Machakos',
        'sub_county': 'Machakos Town',
        'ward': 'Machakos Central',
        'location_text': 'Market Lane',
        'is_local_seller': 'on',
        'local_delivery_scope': 'county',
        'local_pickup_available': 'on',
        'local_pickup_instructions': 'Workshop desk',
    })
    assert response.status_code == 302
    assert response.url == reverse('shops:dashboard')

    shop = Shop.objects.get(name='Machakos Woodcrafts')
    assert shop.county == 'Machakos'
    assert shop.sub_county == 'Machakos Town'
    assert shop.ward == 'Machakos Central'
    assert shop.is_local_seller is True
    assert shop.local_delivery_scope == 'county'
    assert shop.local_pickup_available is True
    assert shop.local_pickup_instructions == 'Workshop desk'


@pytest.mark.django_db
def test_seller_dashboard_local_settings_view(client, seller_user, local_shop):
    client.force_login(seller_user)

    url = reverse('shops:dashboard_local')
    response = client.get(url)
    assert response.status_code == 200
    assert 'Ziuza Local Seller Profile' in response.content.decode()

    # Update local settings
    response_post = client.post(url, {
        'is_local_seller': 'on',
        'county': 'Nairobi',
        'sub_county': 'Westlands',
        'ward': 'Karura',
        'village': 'Gigiri Close',
        'location_text': 'Near Village Market',
        'local_delivery_scope': 'sub_county',
        'local_pickup_available': 'on',
        'local_pickup_instructions': 'Call 0712345678 upon arrival at the gate.',
    })
    assert response_post.status_code == 302
    assert response_post.url == reverse('shops:dashboard_local')

    local_shop.refresh_from_db()
    assert local_shop.ward == 'Karura'
    assert local_shop.village == 'Gigiri Close'
    assert local_shop.location_text == 'Near Village Market'
    assert local_shop.local_delivery_scope == 'sub_county'
    assert local_shop.local_pickup_instructions == 'Call 0712345678 upon arrival at the gate.'


@pytest.mark.django_db
def test_public_shop_and_shop_card_local_badge(client, local_shop):
    url = reverse('shops:public_shop', kwargs={'slug': local_shop.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert 'Ziuza Local' in response.content.decode()
