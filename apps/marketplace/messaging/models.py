import logging
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.marketplace.shops.permissions import MANAGE_MESSAGES, ensure_shop_permission, user_has_shop_permission, user_is_shop_staff


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='conversations')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations')
    listing = models.ForeignKey(
        'listings.Listing',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='conversations',
    )
    subject = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('shop', 'buyer', 'listing')]
        ordering = ['-updated_at']


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class CustomOrderRequest(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        DISCUSSING = 'discussing', 'Discussing'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='custom_order_requests')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='custom_order_requests')
    listing = models.ForeignKey('listings.Listing', null=True, blank=True, on_delete=models.SET_NULL, related_name='custom_order_requests')
    description = models.TextField()
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    needed_by = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    seller_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


@transaction.atomic
def start_or_get_conversation(*, actor, shop, listing=None, subject: str = '') -> Conversation:
    if user_is_shop_staff(actor=actor, shop=shop):
        raise ValidationError('You cannot message your own shop.')
    conversation, _ = Conversation.objects.get_or_create(
        shop=shop,
        buyer=actor,
        listing=listing,
        defaults={'subject': (subject or (listing.title if listing else shop.name))[:200]},
    )
    return conversation


@transaction.atomic
def send_message(*, actor, conversation: Conversation, body: str) -> Message:
    body = (body or '').strip()
    if not body:
        raise ValidationError('Message cannot be empty.')
    is_buyer = conversation.buyer_id == actor.id
    is_seller = user_has_shop_permission(actor=actor, shop=conversation.shop, permission=MANAGE_MESSAGES)
    if not (is_buyer or is_seller):
        raise PermissionDenied('Not a participant in this conversation.')
    message = Message.objects.create(conversation=conversation, sender=actor, body=body)
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=['updated_at'])
    try:
        from apps.marketplace.notifications.services import notify

        recipient = conversation.shop.owner if is_buyer else conversation.buyer
        notify(
            recipient=recipient,
            type='message',
            title='New message',
            body=body[:120],
            target_url=f'/account/messages/{conversation.id}/',
        )
    except Exception:
        # Best-effort notification — message delivery must not fail on notify errors.
        logging.getLogger(__name__).exception('Message notification failed for conversation %s', conversation.id)
    if is_seller:
        from apps.marketplace.shops.team_services import audit_shop_action
        audit_shop_action(
            shop=conversation.shop, actor=actor, action='message.sent', target=conversation,
            description=f'Replied to conversation “{conversation.subject or conversation.id}”.',
        )
    return message


@transaction.atomic
def create_custom_order_request(*, actor, shop, description, listing=None, budget=None, needed_by=None):
    if user_is_shop_staff(actor=actor, shop=shop):
        raise ValidationError('You cannot request a custom order from your own shop.')
    description = description.strip()
    if len(description) < 20:
        raise ValidationError('Describe your request in at least 20 characters.')
    request = CustomOrderRequest.objects.create(
        shop=shop, buyer=actor, listing=listing, description=description,
        budget=budget, needed_by=needed_by,
    )
    from apps.marketplace.notifications.services import notify
    notify(recipient=shop.owner, type='custom_order', title='New custom-order request', body=description[:120], target_url='/seller/custom-orders/')
    return request


@transaction.atomic
def respond_to_custom_order(*, actor, custom_request, response, status):
    ensure_shop_permission(actor=actor, shop=custom_request.shop, permission=MANAGE_MESSAGES)
    if status not in {CustomOrderRequest.Status.DISCUSSING, CustomOrderRequest.Status.ACCEPTED, CustomOrderRequest.Status.DECLINED}:
        raise ValidationError('Choose a valid response status.')
    custom_request.seller_response = response.strip()
    custom_request.status = status
    custom_request.save(update_fields=['seller_response', 'status', 'updated_at'])
    from apps.marketplace.notifications.services import notify
    notify(
        recipient=custom_request.buyer, type='custom_order_response',
        title=f'{custom_request.shop.name} responded to your request',
        body=response[:120], target_url='/account/custom-orders/',
    )
    from apps.marketplace.shops.team_services import audit_shop_action
    audit_shop_action(
        shop=custom_request.shop, actor=actor, action='custom_order.responded', target=custom_request,
        description=f'Responded to custom order from {custom_request.buyer.email}.',
    )
    return custom_request
