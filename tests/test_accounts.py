import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Address
from apps.accounts.services import create_address, register_user

User = get_user_model()

PASSWORD = 'SecurePassword123!'


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email='buyer@ziuza.co.ke',
        password=PASSWORD,
        display_name='Buyer One',
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email='other@ziuza.co.ke',
        password=PASSWORD,
        display_name='Other Buyer',
    )


@pytest.mark.django_db
def test_register_creates_user_and_logs_in(client):
    url = reverse('accounts:register')
    response = client.post(
        url,
        {
            'email': 'newmaker@ziuza.co.ke',
            'display_name': 'New Maker',
            'phone': '+254700000000',
            'password1': PASSWORD,
            'password2': PASSWORD,
        },
    )
    assert response.status_code == 302
    assert response.url == reverse('accounts:account_home')
    assert User.objects.filter(email='newmaker@ziuza.co.ke').exists()
    follow = client.get(response.url)
    assert follow.status_code == 200
    assert b'Habari' in follow.content or b'Your account' in follow.content


@pytest.mark.django_db
def test_register_rejects_duplicate_email(client, user):
    response = client.post(
        reverse('accounts:register'),
        {
            'email': user.email,
            'display_name': 'Dup',
            'password1': PASSWORD,
            'password2': PASSWORD,
        },
    )
    assert response.status_code == 200
    assert b'already exists' in response.content


@pytest.mark.django_db
def test_account_home_hub(client, user):
    client.force_login(user)
    response = client.get(reverse('accounts:account_home'))
    assert response.status_code == 200
    assert b'Orders' in response.content
    assert b'Favorites' in response.content
    assert b'Notifications' in response.content


@pytest.mark.django_db
def test_login_and_logout(client, user):
    login_url = reverse('accounts:login')
    response = client.post(login_url, {'email': user.email, 'password': PASSWORD})
    assert response.status_code == 302
    assert response.url == reverse('accounts:account_home')

    logout_response = client.post(reverse('accounts:logout'))
    assert logout_response.status_code == 302
    assert logout_response.url == reverse('core:home')

    profile = client.get(reverse('accounts:profile'))
    assert profile.status_code == 302
    assert reverse('accounts:login') in profile.url


@pytest.mark.django_db
def test_login_rejects_open_redirect(client, user):
    login_url = reverse('accounts:login') + '?next=https://evil.example/phish'
    response = client.post(login_url, {'email': user.email, 'password': PASSWORD})
    assert response.status_code in (302, 303)
    assert 'evil.example' not in response['Location']


@pytest.mark.django_db
def test_login_rejects_bad_password(client, user):
    response = client.post(
        reverse('accounts:login'),
        {'email': user.email, 'password': 'WrongPassword999!'},
    )
    assert response.status_code == 200
    assert b'Invalid email or password' in response.content


@pytest.mark.django_db
def test_profile_requires_login(client):
    response = client.get(reverse('accounts:profile'))
    assert response.status_code == 302
    assert reverse('accounts:login') in response.url


@pytest.mark.django_db
def test_profile_update_authorized(client, user):
    client.force_login(user)
    response = client.post(
        reverse('accounts:profile'),
        {
            'display_name': 'Updated Name',
            'first_name': 'Amina',
            'last_name': 'Wanjiku',
            'phone': '+254711111111',
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.display_name == 'Updated Name'
    assert user.first_name == 'Amina'
    assert user.phone == '+254711111111'


@pytest.mark.django_db
def test_address_create_and_list(client, user):
    client.force_login(user)
    response = client.post(
        reverse('accounts:address_create'),
        {
            'recipient_name': 'Amina Wanjiku',
            'phone': '+254700000001',
            'address_line_1': '12 Biashara Street',
            'address_line_2': '',
            'city_or_town': 'Nairobi',
            'county': 'Nairobi',
            'postal_code': '00100',
            'country': 'Kenya',
            'is_default_shipping': 'on',
            'is_default_billing': 'on',
        },
    )
    assert response.status_code == 302
    assert Address.objects.filter(user=user).count() == 1

    listing = client.get(reverse('accounts:address_list'))
    assert listing.status_code == 200
    assert b'Amina Wanjiku' in listing.content
    assert b'Biashara Street' in listing.content


@pytest.mark.django_db
def test_address_ownership_blocks_other_user(client, user, other_user):
    address = create_address(
        actor=user,
        recipient_name='Owner',
        phone='+254700000002',
        address_line_1='Owned Lane',
        city_or_town='Kisumu',
        county='Kisumu',
        country='Kenya',
    )

    client.force_login(other_user)
    edit = client.get(reverse('accounts:address_edit', kwargs={'address_id': address.id}))
    assert edit.status_code == 404

    delete = client.post(reverse('accounts:address_delete', kwargs={'address_id': address.id}))
    assert delete.status_code == 404
    assert Address.objects.filter(id=address.id).exists()


@pytest.mark.django_db
def test_register_user_service_normalizes_email(db):
    user = register_user(
        email='  Maker@Ziuza.CO.KE ',
        password=PASSWORD,
        display_name='Maker',
    )
    assert user.email == 'maker@ziuza.co.ke'


@pytest.mark.django_db
def test_create_user_with_email_success():
    email = 'artisan@ziuza.co.ke'
    display_name = 'Nairobi Craftsman'
    user = User.objects.create_user(email=email, password=PASSWORD, display_name=display_name)
    assert user.email == email
    assert user.display_name == display_name
    assert isinstance(user.id, uuid.UUID)
    assert user.check_password(PASSWORD) is True
    assert user.is_staff is False


@pytest.mark.django_db
def test_create_user_without_email_raises_error():
    with pytest.raises(ValueError, match='The Email field must be set'):
        User.objects.create_user(email='', password='password123')


@pytest.mark.django_db
def test_create_superuser():
    admin_user = User.objects.create_superuser(email='admin@ziuza.co.ke', password=PASSWORD)
    assert admin_user.is_staff is True
    assert admin_user.is_superuser is True
