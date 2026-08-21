import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.marketplace.shops.models import ModerationAction, ReportStatus, Shop, ShopVerificationStatus
from apps.marketplace.shops.services import create_shop, update_shop_settings
from apps.marketplace.shops.trust_services import create_report, moderate_report, review_verification, submit_verification

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email='seller@ziuza.co.ke',
        password=PASSWORD,
        display_name='Seller',
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email='other-seller@ziuza.co.ke',
        password=PASSWORD,
        display_name='Other',
    )


@pytest.fixture
def shop(user):
    return create_shop(
        actor=user,
        name='Nairobi Craftsmen',
        description='Handmade goods',
        county='Nairobi',
    )


@pytest.mark.django_db
def test_dashboard_overview_shows_zero_sales_before_orders(client, user, shop):
    client.force_login(user)
    response = client.get(reverse('shops:dashboard'))
    assert response.status_code == 200
    assert b'Recent orders' in response.content
    assert b'Awaiting first paid sale' in response.content or b'KSh 0' in response.content


@pytest.mark.django_db
def test_sell_entry_redirects_to_onboarding_without_shop(client, user):
    client.force_login(user)
    response = client.get(reverse('shops:sell_entry'))
    assert response.status_code == 302
    assert response.url == reverse('shops:onboarding')


@pytest.mark.django_db
def test_onboarding_creates_shop_and_opens_dashboard(client, user):
    client.force_login(user)
    response = client.post(
        reverse('shops:onboarding'),
        {
            'name': 'Kisii Stone Studio',
            'description': 'Soapstone carvings',
            'county': 'Kisii',
            'location_text': 'Kisii Town',
        },
    )
    assert response.status_code == 302
    assert response.url == reverse('shops:dashboard')
    shop = Shop.objects.get(owner=user)
    assert shop.name == 'Kisii Stone Studio'
    assert shop.slug.startswith('kisii-stone-studio')
    assert shop.verification_status == ShopVerificationStatus.UNVERIFIED


@pytest.mark.django_db
def test_dashboard_requires_shop(client, user):
    client.force_login(user)
    response = client.get(reverse('shops:dashboard'))
    assert response.status_code == 302
    assert response.url == reverse('shops:onboarding')


@pytest.mark.django_db
def test_dashboard_overview_for_owner(client, user, shop):
    client.force_login(user)
    response = client.get(reverse('shops:dashboard'))
    assert response.status_code == 200
    assert b'Overview' in response.content
    assert shop.name.encode() in response.content
    assert b'Listings' in response.content
    assert b'Shop settings' in response.content


@pytest.mark.django_db
def test_dashboard_sections_render(client, user, shop):
    client.force_login(user)
    for name in [
        'orders:seller_list',
        'shops:dashboard_reviews',
        'messaging:seller_inbox',
        'analytics:seller',
    ]:
        response = client.get(reverse(name))
        assert response.status_code == 200


@pytest.mark.django_db
def test_shop_settings_update(client, user, shop):
    client.force_login(user)
    response = client.post(
        reverse('shops:dashboard_shop'),
        {
            'name': 'Nairobi Craftsmen Collective',
            'description': 'Updated story',
            'county': 'Nairobi',
            'location_text': 'Eastleigh',
            'policies': 'Returns within 7 days',
            'vacation_mode': 'on',
            'is_active': 'on',
        },
    )
    assert response.status_code == 302
    shop.refresh_from_db()
    assert shop.name == 'Nairobi Craftsmen Collective'
    assert shop.vacation_mode is True
    assert shop.policies.startswith('Returns')


@pytest.mark.django_db
def test_other_user_cannot_open_owner_dashboard_as_their_shop(client, user, other_user, shop):
    """Other user without a shop is sent to onboarding — never sees owner's data."""
    client.force_login(other_user)
    response = client.get(reverse('shops:dashboard'))
    assert response.status_code == 302
    assert response.url == reverse('shops:onboarding')


@pytest.mark.django_db
def test_update_shop_settings_denies_non_owner(user, other_user, shop):
    from django.core.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        update_shop_settings(
            actor=other_user,
            shop=shop,
            name='Hijacked',
        )


@pytest.mark.django_db
def test_public_shop_page(client, shop):
    response = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}))
    assert response.status_code == 200
    assert shop.name.encode() in response.content


@pytest.mark.django_db
def test_suspended_shop_not_public(client, shop):
    shop.verification_status = ShopVerificationStatus.SUSPENDED
    shop.save(update_fields=['verification_status'])
    response = client.get(reverse('shops:public_shop', kwargs={'slug': shop.slug}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get(reverse('shops:dashboard'))
    assert response.status_code == 302
    assert reverse('accounts:login') in response.url


@pytest.mark.django_db
def test_verification_stores_only_suffix_and_staff_review_is_audited(user, shop):
    application = submit_verification(
        actor=user,
        shop=shop,
        legal_name='Nairobi Craftsmen Limited',
        identity_type='national_id',
        identity_last4='1234',
        contact_phone='0712345678',
        consent_confirmed=True,
    )
    shop.refresh_from_db()
    assert application.identity_last4 == '1234'
    assert shop.verification_status == ShopVerificationStatus.PENDING

    moderator = User.objects.create_superuser(email='moderator@ziuza.co.ke', password=PASSWORD)
    review_verification(actor=moderator, application=application, approved=True, notes='Identity reviewed.')
    shop.refresh_from_db()
    assert shop.verification_status == ShopVerificationStatus.VERIFIED
    assert ModerationAction.objects.filter(action=ModerationAction.Action.VERIFY_SHOP, shop=shop).exists()
    assert user.notifications.filter(type='verification_reviewed').exists()


@pytest.mark.django_db
def test_admin_verification_panel_reviews_pending_shop(client, user, shop):
    application = submit_verification(
        actor=user,
        shop=shop,
        legal_name='Nairobi Craftsmen Limited',
        identity_type='business',
        identity_last4='K123',
        contact_phone='0712345678',
        business_registration_number='CPR/2026/12345',
        consent_confirmed=True,
    )
    moderator = User.objects.create_superuser(email='verification-admin@ziuza.co.ke', password=PASSWORD)
    client.force_login(moderator)

    queue = client.get(reverse('admin:shops_verificationapplication_changelist'))
    assert queue.status_code == 200
    assert b'Shop verification' in queue.content
    assert b'Pending review' in queue.content
    assert shop.name.encode() in queue.content

    review_url = reverse('admin:shops_verificationapplication_review', args=[application.id])
    review_page = client.get(review_url)
    assert review_page.status_code == 200
    assert b'Administrator decision' in review_page.content
    assert b'Approve verification' in review_page.content
    assert b'K123' in review_page.content

    decision = client.post(review_url, {'decision': 'approve', 'notes': 'Identity and registration confirmed.'})
    assert decision.status_code == 302
    shop.refresh_from_db()
    application.refresh_from_db()
    assert shop.verification_status == ShopVerificationStatus.VERIFIED
    assert application.reviewed_by == moderator
    assert ModerationAction.objects.filter(
        actor=moderator, shop=shop, action=ModerationAction.Action.VERIFY_SHOP,
    ).exists()


@pytest.mark.django_db
def test_rejected_verification_requires_admin_guidance(user, shop):
    application = submit_verification(
        actor=user,
        shop=shop,
        legal_name='Nairobi Craftsmen Limited',
        identity_type='national_id',
        identity_last4='1234',
        contact_phone='0712345678',
        consent_confirmed=True,
    )
    moderator = User.objects.create_superuser(email='review-guidance@ziuza.co.ke', password=PASSWORD)

    with pytest.raises(ValidationError, match='Explain what the seller needs to correct'):
        review_verification(actor=moderator, application=application, approved=False, notes='')

    application.refresh_from_db()
    shop.refresh_from_db()
    assert application.status == 'pending'
    assert shop.verification_status == ShopVerificationStatus.PENDING


@pytest.mark.django_db
def test_non_owner_cannot_submit_shop_verification(user, other_user, shop):
    with pytest.raises(PermissionDenied):
        submit_verification(
            actor=other_user,
            shop=shop,
            legal_name='Wrong Person',
            identity_type='national_id',
            identity_last4='9999',
            contact_phone='0712345678',
            consent_confirmed=True,
        )


@pytest.mark.django_db
def test_report_can_hide_listing_and_records_moderator_action(user, other_user, shop):
    from decimal import Decimal

    from apps.marketplace.categories.models import Category
    from apps.marketplace.listings.models import ListingStatus
    from apps.marketplace.listings.services import create_listing, publish_listing

    category = Category.objects.create(name='Reported goods', slug='reported-goods', is_visible=True)
    listing = create_listing(
        actor=user,
        shop=shop,
        category=category,
        title='Reported Basket',
        base_price=Decimal('1000.00'),
        quantity_available=2,
    )
    publish_listing(actor=user, listing=listing)
    report = create_report(
        actor=other_user,
        listing=listing,
        reason='misleading',
        details='The material claims appear inconsistent with the photographs.',
    )
    moderator = User.objects.create_superuser(email='trust@ziuza.co.ke', password=PASSWORD)
    moderate_report(actor=moderator, report=report, action=ModerationAction.Action.HIDE_LISTING, notes='Hidden pending evidence review.')
    listing.refresh_from_db()
    report.refresh_from_db()
    assert listing.status == ListingStatus.PAUSED
    assert report.status == ReportStatus.ACTIONED
    assert ModerationAction.objects.filter(report=report, action=ModerationAction.Action.HIDE_LISTING).exists()

    with pytest.raises(ValidationError):
        create_report(actor=user, listing=listing, reason='other', details='An owner cannot report their own listing here.')
