from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.models import Address, User
from apps.accounts.permissions import ensure_authenticated


@transaction.atomic
def create_address(*, actor: User, **address_data) -> Address:
    """Create an address for the actor and enforce single default shipping/billing."""
    ensure_authenticated(actor=actor)
    user = actor

    is_default_shipping = bool(address_data.get('is_default_shipping', False))
    is_default_billing = bool(address_data.get('is_default_billing', False))

    if not Address.objects.filter(user=user).exists():
        is_default_shipping = True
        is_default_billing = True
        address_data['is_default_shipping'] = True
        address_data['is_default_billing'] = True

    if is_default_shipping:
        Address.objects.filter(user=user, is_default_shipping=True).update(is_default_shipping=False)

    if is_default_billing:
        Address.objects.filter(user=user, is_default_billing=True).update(is_default_billing=False)

    return Address.objects.create(user=user, **address_data)


@transaction.atomic
def update_address(*, actor: User, address_id, **address_data) -> Address:
    """Update an owned address. Unauthorized IDs raise PermissionDenied."""
    ensure_authenticated(actor=actor)
    try:
        address = Address.objects.get(id=address_id, user=actor)
    except Address.DoesNotExist as exc:
        raise PermissionDenied('You are not authorized to edit this address.') from exc

    is_default_shipping = bool(address_data.get('is_default_shipping', False))
    is_default_billing = bool(address_data.get('is_default_billing', False))

    if is_default_shipping:
        Address.objects.filter(user=actor, is_default_shipping=True).exclude(id=address.id).update(
            is_default_shipping=False
        )

    if is_default_billing:
        Address.objects.filter(user=actor, is_default_billing=True).exclude(id=address.id).update(
            is_default_billing=False
        )

    for field, value in address_data.items():
        setattr(address, field, value)

    address.save()
    return address


@transaction.atomic
def delete_address(*, actor: User, address_id) -> bool:
    """Delete an owned address and promote defaults when needed."""
    ensure_authenticated(actor=actor)
    try:
        address = Address.objects.get(id=address_id, user=actor)
    except Address.DoesNotExist as exc:
        raise PermissionDenied('You are not authorized to delete this address.') from exc

    was_default_shipping = address.is_default_shipping
    was_default_billing = address.is_default_billing
    address.delete()

    remaining = Address.objects.filter(user=actor).first()
    if remaining:
        updates = []
        if was_default_shipping and not Address.objects.filter(user=actor, is_default_shipping=True).exists():
            remaining.is_default_shipping = True
            updates.append('is_default_shipping')
        if was_default_billing and not Address.objects.filter(user=actor, is_default_billing=True).exists():
            remaining.is_default_billing = True
            updates.append('is_default_billing')
        if updates:
            remaining.save(update_fields=[*updates, 'updated_at'])

    return True
