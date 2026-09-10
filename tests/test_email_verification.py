"""Email OTP verification: signup gate, code lifecycle, resend, login gate."""

import hashlib
import re
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import EmailOTP
from apps.accounts.services import issue_email_otp, verify_email_otp
from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.shops.models import Shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture(autouse=True)
def require_email_verification(settings):
    settings.REQUIRE_EMAIL_VERIFICATION = True


@pytest.fixture
def user(db):
    return User.objects.create_user(email='otp-user@ziuza.co.ke', password=PASSWORD, display_name='Otp User')


def _code_from_email(message) -> str:
    match = re.search(r'\b(\d{6})\b', message.body)
    assert match, f'No 6-digit code found in email body:\n{message.body}'
    return match.group(1)


# --- service -------------------------------------------------------------------

def test_issue_email_otp_sends_six_digit_code(user):
    code = issue_email_otp(user=user)

    assert code is not None and len(code) == 6 and code.isdigit()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    assert code in mail.outbox[0].body
    assert EmailOTP.objects.filter(user=user, consumed_at__isnull=True).exists()


def test_email_otp_uses_keyed_per_record_digest(user):
    code = issue_email_otp(user=user)
    otp = EmailOTP.objects.get(user=user)

    assert otp.code_digest != hashlib.sha256(code.encode('utf-8')).hexdigest()


def test_identical_codes_for_two_users_have_distinct_digests(user):
    other = User.objects.create_user(email='other-otp@ziuza.co.ke', password=PASSWORD)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr('apps.accounts.services.verification_service.secrets.randbelow', lambda _limit: 123456)
        issue_email_otp(user=user)
        issue_email_otp(user=other)

    digests = list(EmailOTP.objects.order_by('user_id').values_list('code_digest', flat=True))
    assert len(digests) == 2
    assert len(set(digests)) == 2


def test_issue_email_otp_is_noop_for_verified_user(user):
    user.email_verified = True
    user.save()
    mail.outbox.clear()

    assert issue_email_otp(user=user) is None
    assert len(mail.outbox) == 0
    assert EmailOTP.objects.count() == 0


def test_verify_email_otp_marks_user_verified(user):
    code = issue_email_otp(user=user)

    assert verify_email_otp(user=user, code=code) is True
    user.refresh_from_db()
    assert user.email_verified is True
    assert user.email_verified_at is not None


def test_wrong_code_rejected_then_correct_code_within_attempts(user):
    code = issue_email_otp(user=user)

    assert verify_email_otp(user=user, code='000000') is False
    assert verify_email_otp(user=user, code=code) is True


def test_code_expires(user):
    code = issue_email_otp(user=user)
    EmailOTP.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

    assert verify_email_otp(user=user, code=code) is False


def test_too_many_attempts_burns_the_code(user):
    code = issue_email_otp(user=user)
    for _ in range(5):
        assert verify_email_otp(user=user, code='000000') is False

    # Attempts exhausted: even the correct code is now refused.
    assert verify_email_otp(user=user, code=code) is False


def test_resend_invalidates_previous_code(user):
    first = issue_email_otp(user=user)
    second = issue_email_otp(user=user)
    assert first != second

    assert verify_email_otp(user=user, code=first) is False
    assert verify_email_otp(user=user, code=second) is True


# --- signup gate ----------------------------------------------------------------

def test_register_redirects_to_otp_page_without_signing_in(client, db):
    response = client.post(
        reverse('accounts:register'),
        {
            'email': 'newbuyer@ziuza.co.ke',
            'display_name': 'New Buyer',
            'password1': PASSWORD,
            'password2': PASSWORD,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse('accounts:verify_email_otp')
    created = User.objects.get(email='newbuyer@ziuza.co.ke')
    assert created.email_verified is False
    # Not authenticated yet — the account is gated behind the code.
    assert not response.wsgi_request.user.is_authenticated
    assert len(mail.outbox) == 1


def test_signup_otp_flow_verifies_and_signs_in(client, db):
    client.post(
        reverse('accounts:register'),
        {
            'email': 'otp-buyer@ziuza.co.ke',
            'display_name': 'Otp Buyer',
            'password1': PASSWORD,
            'password2': PASSWORD,
        },
    )
    code = _code_from_email(mail.outbox[0])

    verify_page = client.get(reverse('accounts:verify_email_otp'))
    assert verify_page.status_code == 200
    assert 'otp-buyer@ziuza.co.ke' in verify_page.content.decode()

    response = client.post(reverse('accounts:verify_email_otp'), {'code': code}, follow=True)

    assert response.status_code == 200
    assert response.wsgi_request.user.is_authenticated
    created = User.objects.get(email='otp-buyer@ziuza.co.ke')
    created.refresh_from_db()
    assert created.email_verified is True


def test_signup_otp_flow_preserves_seller_destination(client, db):
    seller_destination = reverse('shops:sell_entry')
    client.post(
        reverse('accounts:register'),
        {
            'email': 'new-seller@ziuza.co.ke',
            'display_name': 'New Seller',
            'password1': PASSWORD,
            'password2': PASSWORD,
            'next': seller_destination,
        },
        REMOTE_ADDR='192.0.2.10',
    )
    code = _code_from_email(mail.outbox[0])

    response = client.post(reverse('accounts:verify_email_otp'), {'code': code})

    assert response.status_code == 302
    assert response.url == seller_destination
    onboarding = client.get(response.url)
    assert onboarding.status_code == 302
    assert onboarding.url == reverse('shops:onboarding')

    shop_response = client.post(reverse('shops:onboarding'), {
        'name': 'Seller Journey Studio',
        'description': 'Handmade goods from Kenya.',
        'county': 'Nairobi',
    })
    assert shop_response.status_code == 302
    assert shop_response.url == reverse('listings:seller_create')
    shop = Shop.objects.get(owner__email='new-seller@ziuza.co.ke')

    listing_page = client.get(shop_response.url)
    assert listing_page.status_code == 200
    assert b'Create your first listing' in listing_page.content
    assert b'Kenyan shillings (KES)' in listing_page.content
    assert b'name="currency"' not in listing_page.content

    category = Category.objects.create(name='Seller Journey Gifts', slug='seller-journey-gifts')
    listing_response = client.post(reverse('listings:seller_create'), {
        'title': 'Handwoven Journey Basket',
        'category': str(category.id),
        'short_description': 'A handwoven Kenyan basket.',
        'description': 'Made by hand using locally sourced fibres.',
        'base_price': '2400.00',
        'currency': 'USD',
        'quantity_available': '3',
    })
    listing = Listing.objects.get(shop=shop)
    assert listing_response.status_code == 302
    assert listing_response.url == reverse('listings:seller_detail', kwargs={'listing_id': listing.id})
    assert listing.currency == 'KES'
    assert listing.status == ListingStatus.DRAFT

    review_page = client.get(listing_response.url)
    assert b'Ready to publish?' in review_page.content
    publish_response = client.post(reverse('listings:seller_publish', kwargs={'listing_id': listing.id}))
    assert publish_response.status_code == 302
    listing.refresh_from_db()
    assert listing.status == ListingStatus.ACTIVE

    public_response = client.get(reverse('listings:detail', kwargs={'slug': listing.slug}))
    assert public_response.status_code == 200
    assert b'Handwoven Journey Basket' in public_response.content


def test_signup_otp_flow_rejects_external_destination(client, db):
    client.post(
        reverse('accounts:register'),
        {
            'email': 'safe-seller@ziuza.co.ke',
            'password1': PASSWORD,
            'password2': PASSWORD,
            'next': 'https://evil.example/phish',
        },
        REMOTE_ADDR='192.0.2.11',
    )
    code = _code_from_email(mail.outbox[0])

    response = client.post(reverse('accounts:verify_email_otp'), {'code': code})

    assert response.status_code == 302
    assert response.url == reverse('accounts:account_home')


def test_registration_signs_in_immediately_when_verification_is_disabled(client, db, settings):
    settings.REQUIRE_EMAIL_VERIFICATION = False
    destination = reverse('shops:sell_entry')

    response = client.post(
        reverse('accounts:register'),
        {
            'email': 'verification-disabled@ziuza.co.ke',
            'password1': PASSWORD,
            'password2': PASSWORD,
            'next': destination,
        },
        REMOTE_ADDR='192.0.2.12',
    )

    assert response.status_code == 302
    assert response.url == destination
    assert response.wsgi_request.user.is_authenticated
    assert mail.outbox == []


def test_verify_page_without_pending_session_redirects_to_login(client, db):
    response = client.get(reverse('accounts:verify_email_otp'))
    assert response.status_code == 302
    assert reverse('accounts:login') in response.url


def test_debug_code_preview_shown_only_in_debug(client, db):
    from django.test import override_settings

    with override_settings(DEBUG=True):
        client.post(
            reverse('accounts:register'),
            {
                'email': 'debug-preview@ziuza.co.ke',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )
        page = client.get(reverse('accounts:verify_email_otp'))
        content = page.content.decode()
        assert 'Dev preview' in content
        assert _code_from_email(mail.outbox[0]) in content

    # With DEBUG off the code is never rendered.
    User.objects.filter(email='debug-preview@ziuza.co.ke').delete()
    with override_settings(DEBUG=False):
        client.post(
            reverse('accounts:register'),
            {
                'email': 'debug-preview@ziuza.co.ke',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )
        page = client.get(reverse('accounts:verify_email_otp'))
        assert 'Dev preview' not in page.content.decode()


def test_resend_view_issues_fresh_code_for_pending_signup(client, db):
    client.post(
        reverse('accounts:register'),
        {
            'email': 'resend-me@ziuza.co.ke',
            'password1': PASSWORD,
            'password2': PASSWORD,
        },
    )
    first_code = _code_from_email(mail.outbox[0])

    response = client.post(reverse('accounts:resend_verification'))
    assert response.status_code == 302
    assert response.url == reverse('accounts:verify_email_otp')
    assert len(mail.outbox) == 2
    second_code = _code_from_email(mail.outbox[1])
    assert second_code != first_code

    # The old code is dead; the new one works.
    assert client.post(reverse('accounts:verify_email_otp'), {'code': first_code}).status_code == 200
    assert not response.wsgi_request.user.is_authenticated
    assert client.post(reverse('accounts:verify_email_otp'), {'code': second_code}, follow=True).status_code == 200
    assert User.objects.get(email='resend-me@ziuza.co.ke').email_verified is True


# --- login gate & banner ----------------------------------------------------------

def test_login_of_unverified_user_redirects_to_otp_page(client, user):
    issue_email_otp(user=user)
    mail.outbox.clear()

    response = client.post(
        reverse('accounts:login'),
        {'email': user.email, 'password': PASSWORD},
    )

    assert response.status_code == 302
    assert response.url == reverse('accounts:verify_email_otp')
    assert not response.wsgi_request.user.is_authenticated
    assert len(mail.outbox) == 1  # a fresh code was sent

    code = _code_from_email(mail.outbox[0])
    response = client.post(reverse('accounts:verify_email_otp'), {'code': code}, follow=True)
    assert response.wsgi_request.user.is_authenticated
    user.refresh_from_db()
    assert user.email_verified is True


def test_unverified_login_otp_flow_preserves_destination(client, user):
    destination = reverse('shops:sell_entry')
    response = client.post(
        reverse('accounts:login'),
        {'email': user.email, 'password': PASSWORD, 'next': destination},
    )
    assert response.url == reverse('accounts:verify_email_otp')
    code = _code_from_email(mail.outbox[0])

    response = client.post(reverse('accounts:verify_email_otp'), {'code': code})

    assert response.status_code == 302
    assert response.url == destination


def test_unverified_login_signs_in_when_verification_is_disabled(client, user, settings):
    settings.REQUIRE_EMAIL_VERIFICATION = False
    response = client.post(
        reverse('accounts:login'),
        {'email': user.email, 'password': PASSWORD},
    )

    assert response.status_code == 302
    assert response.url == reverse('accounts:account_home')
    assert response.wsgi_request.user.is_authenticated
    assert mail.outbox == []


@override_settings(REQUIRE_EMAIL_VERIFICATION=True)
def test_existing_unverified_session_is_redirected_to_otp_gate(client, user):
    client.force_login(user)

    response = client.get(reverse('accounts:account_home'))

    assert response.status_code == 302
    assert response.url == reverse('accounts:verify_email_otp')
    assert client.session['pending_verification_user_id'] == str(user.id)


def test_login_of_verified_user_goes_stright_to_account(client, user):
    user.email_verified = True
    user.save()

    response = client.post(
        reverse('accounts:login'),
        {'email': user.email, 'password': PASSWORD},
    )

    assert response.status_code == 302
    assert response.url == reverse('accounts:account_home')


def test_account_home_banner_offers_verify_now(client, user, settings):
    settings.REQUIRE_EMAIL_VERIFICATION = False
    client.force_login(user)
    page = client.get(reverse('accounts:account_home'))
    assert 'Verify now' in page.content.decode()

    response = client.post(reverse('accounts:resend_verification'))
    assert response.status_code == 302
    assert response.url == reverse('accounts:verify_email_otp')
    assert len(mail.outbox) == 1
