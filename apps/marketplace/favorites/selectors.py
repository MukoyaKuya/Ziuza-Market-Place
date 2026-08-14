from apps.marketplace.favorites.models import Favorite, ShopFollow


def favorited_listing_ids(*, user, listing_ids) -> set:
    """IDs of the given listings that the user has favorited (empty for guests)."""
    if not getattr(user, 'is_authenticated', False) or not listing_ids:
        return set()
    return set(
        Favorite.objects.filter(
            user=user,
            listing_id__in=list(listing_ids),
        ).values_list('listing_id', flat=True)
    )


def is_listing_favorited(*, user, listing) -> bool:
    """Whether the user has favorited this listing (False for guests)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return Favorite.objects.filter(user=user, listing=listing).exists()


def follows_shop(*, user, shop) -> bool:
    """Whether the user follows this shop (False for guests)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return ShopFollow.objects.filter(user=user, shop=shop).exists()
