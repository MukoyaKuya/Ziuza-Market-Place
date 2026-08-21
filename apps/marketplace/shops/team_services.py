import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.marketplace.notifications.services import notify
from apps.marketplace.shops.models import (
    ShopAuditEvent,
    ShopInvitation,
    ShopMembership,
    ShopMembershipStatus,
    ShopTeamRole,
)
from apps.marketplace.shops.permissions import ensure_shop_owner

User = get_user_model()


def audit_shop_action(*, shop, actor, action, description, target=None, metadata=None):
    return ShopAuditEvent.objects.create(
        shop=shop,
        actor=actor,
        action=action[:80],
        target_type=target.__class__.__name__[:40] if target is not None else '',
        target_id=str(target.pk)[:64] if target is not None else '',
        description=description[:300],
        metadata=metadata or {},
    )


def _digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


@transaction.atomic
def invite_team_member(*, actor, shop, email, role):
    ensure_shop_owner(actor=actor, shop=shop)
    email = User.objects.normalize_email((email or '').strip())
    if role not in ShopTeamRole.values:
        raise ValidationError('Choose a valid team role.')
    try:
        invitee = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist as exc:
        raise ValidationError('Invitee must already have an active Ziuza account.') from exc
    if invitee.id == shop.owner_id:
        raise ValidationError('The shop owner already has full access.')
    if invitee.shop_memberships.filter(status=ShopMembershipStatus.ACTIVE).exists() or hasattr(invitee, 'shop'):
        raise ValidationError('This account already manages another shop.')
    ShopInvitation.objects.filter(shop=shop, email__iexact=email, accepted_at__isnull=True, revoked_at__isnull=True).update(revoked_at=timezone.now())
    token = secrets.token_urlsafe(32)
    invitation = ShopInvitation.objects.create(
        shop=shop,
        email=email,
        role=role,
        token_digest=_digest(token),
        invited_by=actor,
        expires_at=timezone.now() + timedelta(days=7),
    )
    notify(
        recipient=invitee,
        type='team_invitation',
        title=f'Invitation to help manage {shop.name}',
        body=f'{actor.get_full_name()} invited you as {invitation.get_role_display()}.',
        target_url=f'/seller/team/accept/{token}/',
    )
    audit_shop_action(
        shop=shop, actor=actor, action='team.invited', target=invitation,
        description=f'Invited {email} as {invitation.get_role_display()}.',
    )
    return invitation, token


def invitation_for_token(*, actor, token):
    invitation = ShopInvitation.objects.select_related('shop', 'invited_by').filter(
        token_digest=_digest(token),
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if invitation is None or invitation.email.casefold() != actor.email.casefold():
        raise ValidationError('This invitation is invalid, expired, or belongs to another account.')
    return invitation


@transaction.atomic
def accept_team_invitation(*, actor, token):
    invitation = invitation_for_token(actor=actor, token=token)
    invitation = ShopInvitation.objects.select_for_update().get(pk=invitation.pk)
    if hasattr(actor, 'shop') or actor.shop_memberships.filter(status=ShopMembershipStatus.ACTIVE).exists():
        raise ValidationError('This account already manages another shop.')
    membership, _ = ShopMembership.objects.update_or_create(
        shop=invitation.shop,
        user=actor,
        defaults={
            'role': invitation.role,
            'status': ShopMembershipStatus.ACTIVE,
            'invited_by': invitation.invited_by,
            'revoked_at': None,
        },
    )
    invitation.accepted_by = actor
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=['accepted_by', 'accepted_at'])
    audit_shop_action(
        shop=invitation.shop, actor=actor, action='team.accepted', target=membership,
        description=f'{actor.email} joined as {membership.get_role_display()}.',
    )
    return membership


@transaction.atomic
def change_team_role(*, actor, shop, membership, role):
    ensure_shop_owner(actor=actor, shop=shop)
    if membership.shop_id != shop.id or role not in ShopTeamRole.values:
        raise ValidationError('Invalid team membership or role.')
    old_role = membership.get_role_display()
    membership.role = role
    membership.save(update_fields=['role'])
    audit_shop_action(
        shop=shop, actor=actor, action='team.role_changed', target=membership,
        description=f'Changed {membership.user.email} from {old_role} to {membership.get_role_display()}.',
    )
    return membership


@transaction.atomic
def revoke_team_member(*, actor, shop, membership):
    ensure_shop_owner(actor=actor, shop=shop)
    if membership.shop_id != shop.id:
        raise ValidationError('Invalid team membership.')
    membership.status = ShopMembershipStatus.REVOKED
    membership.revoked_at = timezone.now()
    membership.save(update_fields=['status', 'revoked_at'])
    audit_shop_action(
        shop=shop, actor=actor, action='team.revoked', target=membership,
        description=f'Revoked access for {membership.user.email}.',
    )
    return membership
