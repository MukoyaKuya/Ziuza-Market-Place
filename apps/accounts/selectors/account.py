def account_summary(*, user) -> dict:
    """Buyer account hub counters — fail soft if marketplace apps are unavailable."""
    from apps.accounts.selectors import list_addresses_for_user
    from apps.marketplace.favorites.models import Favorite
    from apps.marketplace.messaging.models import Conversation
    from apps.marketplace.notifications.models import Notification
    from apps.marketplace.orders.models import Order
    from apps.marketplace.search.models import SavedSearch
    from apps.marketplace.shops.selectors import get_shop_for_user

    return {
        'order_count': Order.objects.filter(buyer=user).count(),
        'favorite_count': Favorite.objects.filter(user=user).count(),
        'saved_search_count': SavedSearch.objects.filter(user=user).count(),
        'message_count': Conversation.objects.filter(buyer=user).count(),
        'unread_notification_count': Notification.objects.filter(recipient=user, is_read=False).count(),
        'address_count': list_addresses_for_user(user=user).count(),
        'has_shop': get_shop_for_user(user=user) is not None,
        'recent_orders': list(Order.objects.filter(buyer=user).prefetch_related('items')[:3]),
    }
