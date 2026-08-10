from django.contrib.auth import get_user_model

from apps.marketplace.shops.models import Shop, ShopVerificationStatus

User = get_user_model()


def get_shop_for_owner(*, user: User) -> Shop | None:
    return Shop.objects.filter(owner=user).first()


def get_shop_for_user(*, user: User) -> Shop | None:
    owned = get_shop_for_owner(user=user)
    if owned is not None:
        return owned
    return Shop.objects.filter(memberships__user=user, memberships__status='active').distinct().first()


def get_public_shop_by_slug(*, slug: str) -> Shop:
    """Public shop page — excludes suspended shops."""
    return Shop.objects.select_related('owner').get(
        slug=slug,
        is_active=True,
    )


def shop_is_publicly_listable(shop: Shop) -> bool:
    return shop.is_publicly_visible and shop.verification_status != ShopVerificationStatus.SUSPENDED
