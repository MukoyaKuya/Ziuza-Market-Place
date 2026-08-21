import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.marketplace.analytics.selectors import shop_analytics_summary
from apps.marketplace.orders.models import (
    CaseResolutionOutcome,
    FulfillmentStatus,
    HelpRequestReason,
    HelpRequestStatus,
    Order,
    OrderItem,
    PaymentStatus,
    ProtectionCaseType,
    RequestedOutcome,
    SellerOrder,
)
from apps.marketplace.orders.support import (
    add_case_evidence,
    add_case_message,
    open_help_request,
    resolve_protection_case,
    seller_respond_to_help_request,
)
from apps.marketplace.shops.models import ShopMembership, ShopTeamRole
from apps.marketplace.shops.services import create_shop

User = get_user_model()
PASSWORD = 'SecurePassword123!'


@pytest.fixture
def protection_setup(db):
    seller = User.objects.create_user(email='case-seller@ziuza.co.ke', password=PASSWORD, display_name='Seller')
    buyer = User.objects.create_user(email='case-buyer@ziuza.co.ke', password=PASSWORD, display_name='Buyer')
    support = User.objects.create_user(email='case-support@ziuza.co.ke', password=PASSWORD, display_name='Support')
    stranger = User.objects.create_user(email='case-stranger@ziuza.co.ke', password=PASSWORD, display_name='Stranger')
    shop = create_shop(actor=seller, name='Protected Studio', county='Nairobi')
    ShopMembership.objects.create(shop=shop, user=support, role=ShopTeamRole.SUPPORT, invited_by=seller)
    order = Order.objects.create(
        public_number=f'CASE-{uuid.uuid4().hex[:8]}', buyer=buyer,
        payment_status=PaymentStatus.PAID, fulfillment_status=FulfillmentStatus.DELIVERED,
        subtotal=Decimal('2500.00'), grand_total=Decimal('2500.00'),
    )
    seller_order = SellerOrder.objects.create(
        order=order, shop=shop, subtotal=Decimal('2500.00'),
        fulfillment_status=FulfillmentStatus.DELIVERED,
    )
    OrderItem.objects.create(
        order=order, seller_order=seller_order, shop=shop,
        title_snapshot='Handmade basket', unit_price=Decimal('2500.00'),
        quantity=1, line_total=Decimal('2500.00'), product_type_snapshot='physical',
    )
    return seller, buyer, support, stranger, shop, order, seller_order


def open_case(buyer, seller_order, **overrides):
    fields = {
        'actor': buyer, 'seller_order': seller_order,
        'reason': HelpRequestReason.DAMAGED,
        'description': 'The basket arrived with a clearly broken handle.',
        'case_type': ProtectionCaseType.BUYER_PROTECTION,
        'requested_outcome': RequestedOutcome.REPLACEMENT,
    }
    fields.update(overrides)
    return open_help_request(**fields)


@pytest.mark.django_db
def test_case_creation_records_deadline_timeline_and_notifies_support_team(protection_setup):
    seller, buyer, support, _, _, _, seller_order = protection_setup
    case = open_case(buyer, seller_order)
    assert case.response_due_at > timezone.now()
    assert case.messages.filter(author=buyer).exists()
    assert case.events.filter(action='case.opened').exists()
    assert seller.notifications.filter(type='help_request').exists()
    assert support.notifications.filter(type='help_request').exists()


@pytest.mark.django_db
def test_return_eligibility_requires_recent_physical_delivery(protection_setup):
    _, buyer, _, _, _, _, seller_order = protection_setup
    seller_order.fulfillment_status = FulfillmentStatus.SHIPPED
    seller_order.save(update_fields=['fulfillment_status'])
    with pytest.raises(ValidationError, match='after delivery'):
        open_case(buyer, seller_order, case_type=ProtectionCaseType.RETURN)

    seller_order.fulfillment_status = FulfillmentStatus.DELIVERED
    seller_order.save(update_fields=['fulfillment_status'])
    SellerOrder.objects.filter(pk=seller_order.pk).update(updated_at=timezone.now() - timedelta(days=15))
    seller_order.refresh_from_db()
    with pytest.raises(ValidationError, match='window has closed'):
        open_case(buyer, seller_order, case_type=ProtectionCaseType.RETURN)


@pytest.mark.django_db
def test_digital_item_cannot_be_physically_returned(protection_setup):
    _, buyer, _, _, _, _, seller_order = protection_setup
    seller_order.items.update(product_type_snapshot='digital')
    with pytest.raises(ValidationError, match='Digital products'):
        open_case(buyer, seller_order, case_type=ProtectionCaseType.EXCHANGE)


@pytest.mark.django_db
def test_seller_response_is_timed_and_discussion_is_audited(protection_setup):
    _, buyer, support, _, shop, _, seller_order = protection_setup
    case = open_case(buyer, seller_order)
    seller_respond_to_help_request(actor=support, case=case, response='We will replace the damaged basket immediately.')
    case.refresh_from_db()
    assert case.status == HelpRequestStatus.SELLER_RESPONDED
    assert case.first_seller_response_at is not None
    assert case.messages.filter(author=support).exists()
    assert buyer.notifications.filter(type='help_request_response').exists()
    summary = shop_analytics_summary(shop=shop)
    assert summary['on_time_case_response_rate'] == 100
    assert summary['protection_case_rate'] == 100.0


@pytest.mark.django_db
def test_private_evidence_is_validated_and_only_case_participants_can_download(client, protection_setup):
    seller, buyer, _, stranger, _, _, seller_order = protection_setup
    case = open_case(buyer, seller_order)
    with pytest.raises(ValidationError, match='JPG'):
        add_case_evidence(
            actor=buyer, case=case,
            uploaded_file=SimpleUploadedFile('unsafe.exe', b'not executable', content_type='application/octet-stream'),
        )
    with pytest.raises(ValidationError, match='do not match'):
        add_case_evidence(
            actor=buyer, case=case,
            uploaded_file=SimpleUploadedFile('spoofed.png', b'not a real image', content_type='image/png'),
        )
    evidence = add_case_evidence(
        actor=buyer, case=case,
        uploaded_file=SimpleUploadedFile('damage.png', b'\x89PNG\r\n\x1a\n evidence', content_type='image/png'),
        description='Broken handle close-up',
    )
    url = reverse('orders:case_evidence_download', kwargs={'evidence_id': evidence.id})
    try:
        client.force_login(stranger)
        assert client.get(url).status_code == 404
        client.force_login(seller)
        response = client.get(url)
        assert response.status_code == 200
        assert 'attachment' in response.headers['Content-Disposition']
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert response.headers['Cache-Control'] == 'private, no-store'
        response.close()
    finally:
        evidence.file.delete(save=False)


@pytest.mark.django_db
def test_outsider_cannot_message_case(protection_setup):
    _, buyer, _, stranger, _, _, seller_order = protection_setup
    case = open_case(buyer, seller_order)
    with pytest.raises(PermissionDenied):
        add_case_message(actor=stranger, case=case, body='I should not be here.')


@pytest.mark.django_db
def test_moderator_resolution_records_recommendation_without_moving_payment(protection_setup):
    _, buyer, _, _, _, order, seller_order = protection_setup
    moderator = User.objects.create_superuser(email='case-moderator@ziuza.co.ke', password=PASSWORD)
    case = open_case(buyer, seller_order)
    resolve_protection_case(
        actor=moderator, case=case, outcome=CaseResolutionOutcome.BUYER,
        notes='Evidence confirms damage in transit and supports the buyer claim.',
        refund_recommendation=Decimal('1250.00'),
    )
    case.refresh_from_db()
    order.refresh_from_db()
    assert case.status == HelpRequestStatus.RESOLVED
    assert case.refund_recommendation == Decimal('1250.00')
    assert case.moderator == moderator
    assert case.events.filter(action='case.resolved').exists()
    assert order.payment_status == PaymentStatus.PAID


@pytest.mark.django_db
def test_refund_recommendation_cannot_exceed_shop_order(protection_setup):
    _, buyer, _, _, _, _, seller_order = protection_setup
    moderator = User.objects.create_superuser(email='case-limit@ziuza.co.ke', password=PASSWORD)
    case = open_case(buyer, seller_order)
    with pytest.raises(ValidationError, match='subtotal'):
        resolve_protection_case(
            actor=moderator, case=case, outcome=CaseResolutionOutcome.BUYER,
            notes='The requested recommendation exceeds the eligible shop subtotal.',
            refund_recommendation=Decimal('2500.01'),
        )


@pytest.mark.django_db
def test_case_pages_support_structured_request_and_shared_timeline(client, protection_setup):
    seller, buyer, _, _, _, _, seller_order = protection_setup
    client.force_login(buyer)
    response = client.post(reverse('orders:buyer_help_create', kwargs={'seller_order_id': seller_order.id}), {
        'case_type': ProtectionCaseType.RETURN,
        'reason': HelpRequestReason.NOT_AS_DESCRIBED,
        'description': 'The delivered weave and dimensions differ from the listing.',
        'requested_outcome': RequestedOutcome.RETURN_REFUND,
        'desired_resolution': 'I would like to return this item.',
    })
    assert response.status_code == 302
    case = seller_order.help_requests.get()
    detail = client.get(reverse('orders:buyer_help_detail', kwargs={'case_id': case.id}))
    assert detail.status_code == 200
    assert b'Return request' in detail.content
    client.force_login(seller)
    seller_detail = client.get(reverse('orders:seller_detail', kwargs={'seller_order_id': seller_order.id}))
    assert seller_detail.status_code == 200
    assert b'Respond by' in seller_detail.content
