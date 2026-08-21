from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.marketplace.notifications.services import notify
from apps.marketplace.orders.models import (
    CaseResolutionOutcome,
    FulfillmentStatus,
    HelpRequest,
    HelpRequestReason,
    HelpRequestStatus,
    PaymentStatus,
    ProtectionCaseEvent,
    ProtectionCaseEvidence,
    ProtectionCaseMessage,
    ProtectionCaseType,
    RequestedOutcome,
    SellerOrder,
)
from apps.marketplace.shops.models import ShopMembershipStatus, ShopTeamRole
from apps.marketplace.shops.permissions import MANAGE_SUPPORT, ensure_shop_permission, user_has_shop_permission

ACTIVE_STATUSES = {HelpRequestStatus.OPEN, HelpRequestStatus.SELLER_RESPONDED, HelpRequestStatus.ESCALATED}
RETURN_WINDOW_DAYS = 14
SELLER_RESPONSE_HOURS = 48
MAX_EVIDENCE_SIZE = 10 * 1024 * 1024
ALLOWED_EVIDENCE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}


def _evidence_signature_matches(uploaded_file, content_type):
    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    return {
        'image/jpeg': header.startswith(b'\xff\xd8\xff'),
        'image/png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'image/webp': header.startswith(b'RIFF') and header[8:12] == b'WEBP',
        'application/pdf': header.startswith(b'%PDF-'),
    }.get(content_type, False)


def _event(*, case, actor, action, note='', is_internal=False, metadata=None):
    return ProtectionCaseEvent.objects.create(
        case=case, actor=actor, action=action, note=note[:300],
        is_internal=is_internal, metadata=metadata or {},
    )


def _notify_shop_support(*, shop, type, title, body='', target_url=''):
    recipient_ids = {shop.owner_id}
    recipient_ids.update(shop.memberships.filter(
        status=ShopMembershipStatus.ACTIVE,
        role__in=[ShopTeamRole.MANAGER, ShopTeamRole.SUPPORT],
    ).values_list('user_id', flat=True))
    from django.contrib.auth import get_user_model
    for recipient in get_user_model().objects.filter(id__in=recipient_ids, is_active=True):
        notify(recipient=recipient, type=type, title=title, body=body, target_url=target_url)


def can_access_case(*, actor, case, allow_internal=False):
    if not getattr(actor, 'is_authenticated', False):
        return False
    if actor.id == case.buyer_id:
        return not allow_internal
    if actor.is_staff:
        return True
    return user_has_shop_permission(actor=actor, shop=case.seller_order.shop, permission=MANAGE_SUPPORT)


def _validate_return_eligibility(*, seller_order, case_type):
    if case_type not in {ProtectionCaseType.RETURN, ProtectionCaseType.EXCHANGE}:
        return
    if seller_order.fulfillment_status != FulfillmentStatus.DELIVERED:
        raise ValidationError('Returns and exchanges become available after delivery is confirmed.')
    if not seller_order.items.exclude(product_type_snapshot='digital').exists():
        raise ValidationError('Digital products are not eligible for physical returns or exchanges.')
    if seller_order.updated_at < timezone.now() - timedelta(days=RETURN_WINDOW_DAYS):
        raise ValidationError(f'The {RETURN_WINDOW_DAYS}-day return and exchange window has closed.')


@transaction.atomic
def open_help_request(*, actor, seller_order: SellerOrder, reason: str, description: str,
                      desired_resolution: str = '', case_type=ProtectionCaseType.SUPPORT,
                      requested_outcome=''):
    if not actor.is_authenticated or seller_order.order.buyer_id != actor.id:
        raise PermissionDenied
    if seller_order.order.payment_status != PaymentStatus.PAID:
        raise ValidationError('Protection cases are available after payment is confirmed.')
    if reason not in HelpRequestReason.values:
        raise ValidationError('Choose a valid reason.')
    if case_type not in ProtectionCaseType.values:
        raise ValidationError('Choose a valid case type.')
    if requested_outcome and requested_outcome not in RequestedOutcome.values:
        raise ValidationError('Choose a valid requested outcome.')
    _validate_return_eligibility(seller_order=seller_order, case_type=case_type)
    description = description.strip()
    if len(description) < 20:
        raise ValidationError('Describe the problem in at least 20 characters.')
    if HelpRequest.objects.filter(seller_order=seller_order, status__in=ACTIVE_STATUSES).exists():
        raise ValidationError('An active protection case already exists for this shop order.')
    case = HelpRequest.objects.create(
        order=seller_order.order, seller_order=seller_order, buyer=actor,
        case_type=case_type, reason=reason, description=description,
        desired_resolution=desired_resolution.strip()[:200],
        requested_outcome=requested_outcome,
        response_due_at=timezone.now() + timedelta(hours=SELLER_RESPONSE_HOURS),
    )
    ProtectionCaseMessage.objects.create(case=case, author=actor, body=description)
    _event(case=case, actor=actor, action='case.opened', note=case.get_case_type_display())
    _notify_shop_support(
        shop=seller_order.shop, type='help_request',
        title=f'Buyer opened a {case.get_case_type_display().lower()} for {seller_order.order.public_number}',
        body=case.get_reason_display(), target_url=f'/seller/orders/{seller_order.id}/',
    )
    return case


@transaction.atomic
def add_case_message(*, actor, case: HelpRequest, body: str, internal=False):
    if not can_access_case(actor=actor, case=case, allow_internal=internal):
        raise PermissionDenied
    if case.status not in ACTIVE_STATUSES:
        raise ValidationError('This case is closed.')
    if internal and not actor.is_staff:
        raise PermissionDenied
    body = body.strip()
    if len(body) < 3:
        raise ValidationError('Enter a message of at least 3 characters.')
    message = ProtectionCaseMessage.objects.create(case=case, author=actor, body=body, is_internal=internal)
    if not internal and actor.id != case.buyer_id:
        if not case.first_seller_response_at:
            case.first_seller_response_at = timezone.now()
        case.seller_response = body
        case.status = HelpRequestStatus.SELLER_RESPONDED
        case.save(update_fields=['first_seller_response_at', 'seller_response', 'status', 'updated_at'])
        notify(
            recipient=case.buyer, type='help_request_response',
            title=f'{case.seller_order.shop.name} responded to your case',
            target_url=f'/account/help/{case.id}/',
        )
    elif not internal:
        _notify_shop_support(
            shop=case.seller_order.shop, type='help_request_message',
            title=f'Buyer updated case {case.order.public_number}',
            target_url=f'/seller/orders/{case.seller_order_id}/',
        )
    _event(case=case, actor=actor, action='case.message_added', is_internal=internal)
    return message


def seller_respond_to_help_request(*, actor, case: HelpRequest, response: str):
    ensure_shop_permission(actor=actor, shop=case.seller_order.shop, permission=MANAGE_SUPPORT)
    return add_case_message(actor=actor, case=case, body=response)


@transaction.atomic
def add_case_evidence(*, actor, case: HelpRequest, uploaded_file, description=''):
    if not can_access_case(actor=actor, case=case):
        raise PermissionDenied
    if case.status not in ACTIVE_STATUSES:
        raise ValidationError('Evidence cannot be added to a closed case.')
    if uploaded_file is None:
        raise ValidationError('Choose an evidence file.')
    if uploaded_file.size > MAX_EVIDENCE_SIZE:
        raise ValidationError('Evidence files must be 10 MB or smaller.')
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    if content_type not in ALLOWED_EVIDENCE_TYPES:
        raise ValidationError('Upload a JPG, PNG, WebP, or PDF file.')
    if not _evidence_signature_matches(uploaded_file, content_type):
        raise ValidationError('The evidence file contents do not match its file type.')
    evidence = ProtectionCaseEvidence.objects.create(
        case=case, uploaded_by=actor, file=uploaded_file,
        original_name=Path(uploaded_file.name).name[:255], content_type=content_type,
        size=uploaded_file.size, description=description.strip()[:300],
    )
    _event(case=case, actor=actor, action='case.evidence_added', note=evidence.original_name)
    return evidence


@transaction.atomic
def escalate_help_request(*, actor, case: HelpRequest):
    if case.buyer_id != actor.id:
        raise PermissionDenied
    if case.status not in {HelpRequestStatus.OPEN, HelpRequestStatus.SELLER_RESPONDED}:
        raise ValidationError('This request cannot be escalated.')
    case.status = HelpRequestStatus.ESCALATED
    case.escalated_at = timezone.now()
    case.save(update_fields=['status', 'escalated_at', 'updated_at'])
    _event(case=case, actor=actor, action='case.escalated', note='Escalated to Ziuza moderation.')
    _notify_shop_support(
        shop=case.seller_order.shop, type='help_request_escalated',
        title=f'Case {case.order.public_number} was escalated',
        target_url=f'/seller/orders/{case.seller_order_id}/',
    )
    return case


@transaction.atomic
def resolve_protection_case(*, actor, case: HelpRequest, outcome: str, notes: str, refund_recommendation=Decimal('0.00')):
    if not actor.is_staff:
        raise PermissionDenied
    if case.status not in ACTIVE_STATUSES:
        raise ValidationError('This case is already closed.')
    if outcome not in CaseResolutionOutcome.values:
        raise ValidationError('Choose a valid resolution outcome.')
    notes = notes.strip()
    if len(notes) < 10:
        raise ValidationError('Provide public resolution notes of at least 10 characters.')
    try:
        amount = Decimal(str(refund_recommendation or '0')).quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise ValidationError('Enter a valid refund recommendation.') from exc
    if amount < 0 or amount > case.seller_order.subtotal:
        raise ValidationError('Refund recommendation must be between zero and the shop order subtotal.')
    now = timezone.now()
    case.status = HelpRequestStatus.RESOLVED
    case.resolution_outcome = outcome
    case.resolution_notes = notes
    case.refund_recommendation = amount
    case.moderator = actor
    case.resolved_at = now
    case.closed_at = now
    case.save(update_fields=[
        'status', 'resolution_outcome', 'resolution_notes', 'refund_recommendation',
        'moderator', 'resolved_at', 'closed_at', 'updated_at',
    ])
    _event(case=case, actor=actor, action='case.resolved', note=case.get_resolution_outcome_display(), metadata={'refund_recommendation': str(amount)})
    notify(
        recipient=case.buyer, type='help_request_resolved',
        title=f'Ziuza resolved your case for {case.order.public_number}',
        target_url=f'/account/help/{case.id}/',
    )
    _notify_shop_support(
        shop=case.seller_order.shop, type='help_request_resolved',
        title=f'Ziuza resolved case {case.order.public_number}',
        target_url=f'/seller/orders/{case.seller_order_id}/',
    )
    return case
