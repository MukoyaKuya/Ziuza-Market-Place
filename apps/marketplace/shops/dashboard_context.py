from apps.marketplace.shops.models import Shop
from apps.marketplace.shops.permissions import (
    MANAGE_LISTINGS,
    MANAGE_MESSAGES,
    MANAGE_PROMOTIONS,
    MANAGE_SHIPPING,
    MANAGE_STOREFRONT,
    VIEW_ANALYTICS,
    VIEW_ORDERS,
    user_has_shop_permission,
)

DASHBOARD_NAV = [
    {'key': 'overview', 'label': 'Overview', 'url_name': 'shops:dashboard'},
    {'key': 'listings', 'label': 'Listings', 'url_name': 'listings:seller_list', 'permission': MANAGE_LISTINGS},
    {'key': 'inventory', 'label': 'Inventory', 'url_name': 'listings:seller_inventory', 'permission': MANAGE_LISTINGS},
    {'key': 'shipping', 'label': 'Shipping profiles', 'url_name': 'shipping:profiles', 'permission': MANAGE_SHIPPING},
    {'key': 'bulk_tools', 'label': 'Bulk tools', 'url_name': 'listings:seller_bulk_tools', 'permission': MANAGE_LISTINGS},
    {'key': 'orders', 'label': 'Orders', 'url_name': 'orders:seller_list', 'permission': VIEW_ORDERS},
    {'key': 'shop', 'label': 'Shop settings', 'url_name': 'shops:dashboard_shop', 'owner_only': True},
    {'key': 'storefront', 'label': 'Storefront', 'url_name': 'shops:storefront', 'permission': MANAGE_STOREFRONT},
    {'key': 'reviews', 'label': 'Reviews', 'url_name': 'shops:dashboard_reviews'},
    {'key': 'messages', 'label': 'Messages', 'url_name': 'messaging:seller_inbox', 'permission': MANAGE_MESSAGES},
    {'key': 'analytics', 'label': 'Analytics', 'url_name': 'analytics:seller', 'permission': VIEW_ANALYTICS},
    {'key': 'verification', 'label': 'Verification', 'url_name': 'shops:verification', 'owner_only': True},
    {'key': 'local', 'label': 'Ziuza Local', 'url_name': 'shops:dashboard_local', 'owner_only': True},
    {'key': 'gifts', 'label': 'Gift Section (Zawadi)', 'url_name': 'shops:dashboard_gifts', 'owner_only': True},
    {'key': 'promotions', 'label': 'Promotions', 'url_name': 'promotions:seller_list', 'permission': MANAGE_PROMOTIONS},
    {'key': 'custom_orders', 'label': 'Custom orders', 'url_name': 'messaging:seller_custom_orders', 'permission': MANAGE_MESSAGES},
    {'key': 'team', 'label': 'Team & activity', 'url_name': 'shops:team'},
]


def dashboard_context(*, shop: Shop, section: str, actor=None, **extra):
    is_owner = actor is not None and shop.owner_id == actor.id
    navigation = [
        item for item in DASHBOARD_NAV
        if not item.get('owner_only') or is_owner
        if not item.get('permission') or user_has_shop_permission(
            actor=actor, shop=shop, permission=item['permission']
        )
    ]
    return {
        'shop': shop,
        'dashboard_nav': navigation,
        'dashboard_section': section,
        'page_title': f'Seller · {shop.name}',
        **extra,
    }
