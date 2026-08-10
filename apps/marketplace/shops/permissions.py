from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import ensure_authenticated
from apps.marketplace.shops.models import Shop, ShopMembershipStatus, ShopTeamRole


MANAGE_LISTINGS = 'manage_listings'
MANAGE_ORDERS = 'manage_orders'
VIEW_ORDERS = 'view_orders'
MANAGE_MESSAGES = 'manage_messages'
MANAGE_SUPPORT = 'manage_support'
MANAGE_SHIPPING = 'manage_shipping'
MANAGE_PROMOTIONS = 'manage_promotions'
MANAGE_STOREFRONT = 'manage_storefront'
VIEW_ANALYTICS = 'view_analytics'

ROLE_PERMISSIONS = {
    ShopTeamRole.MANAGER: {
        MANAGE_LISTINGS, MANAGE_ORDERS, VIEW_ORDERS, MANAGE_MESSAGES, MANAGE_SUPPORT,
        MANAGE_SHIPPING, MANAGE_PROMOTIONS, MANAGE_STOREFRONT, VIEW_ANALYTICS,
    },
    ShopTeamRole.CATALOG: {
        MANAGE_LISTINGS, MANAGE_SHIPPING, MANAGE_PROMOTIONS, MANAGE_STOREFRONT, VIEW_ANALYTICS,
    },
    ShopTeamRole.ORDERS: {MANAGE_ORDERS, VIEW_ORDERS, VIEW_ANALYTICS},
    ShopTeamRole.SUPPORT: {VIEW_ORDERS, MANAGE_MESSAGES, MANAGE_SUPPORT},
}


def ensure_shop_owner(*, actor: AbstractBaseUser, shop: Shop) -> Shop:
    """Sensitive shop identity, team, and verification actions remain owner-only."""
    ensure_authenticated(actor=actor)
    if shop.owner_id != actor.id:
        raise PermissionDenied('Only the shop owner can perform this action.')
    return shop


def user_has_shop_permission(*, actor, shop, permission) -> bool:
    if not getattr(actor, 'is_authenticated', False):
        return False
    if shop.owner_id == actor.id:
        return True
    membership = shop.memberships.filter(user=actor, status=ShopMembershipStatus.ACTIVE).only('role').first()
    return bool(membership and permission in ROLE_PERMISSIONS.get(membership.role, set()))


def user_is_shop_staff(*, actor, shop) -> bool:
    if not getattr(actor, 'is_authenticated', False):
        return False
    return shop.owner_id == actor.id or shop.memberships.filter(
        user=actor, status=ShopMembershipStatus.ACTIVE
    ).exists()


def ensure_shop_permission(*, actor, shop, permission) -> Shop:
    ensure_authenticated(actor=actor)
    if not user_has_shop_permission(actor=actor, shop=shop, permission=permission):
        raise PermissionDenied('Your shop role does not allow this action.')
    return shop


def get_owned_shop_or_deny(*, actor: AbstractBaseUser) -> Shop:
    ensure_authenticated(actor=actor)
    try:
        return Shop.objects.get(owner=actor)
    except Shop.DoesNotExist as exc:
        raise PermissionDenied('Create a shop before accessing the seller dashboard.') from exc
