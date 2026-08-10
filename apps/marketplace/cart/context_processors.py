from apps.marketplace.cart.services import annotate_cart_totals, get_or_create_cart


def cart_summary(request):
    """Expose cart item count for navbar without raising on early middleware."""
    try:
        if not hasattr(request, 'session'):
            return {'cart_item_count': 0}
        cart = get_or_create_cart(request=request)
        totals = annotate_cart_totals(cart)
        return {'cart_item_count': totals['item_count']}
    except Exception:
        return {'cart_item_count': 0}
