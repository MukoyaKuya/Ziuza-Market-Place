from django.db.models import Avg, Count, Prefetch, Q

from apps.marketplace.listings.models import Inventory, Listing, ListingStatus


def seller_listings_for_shop(*, shop):
    return (
        Listing.objects.filter(shop=shop)
        .select_related('category')
        .prefetch_related(
            Prefetch(
                'inventory_rows',
                queryset=Inventory.objects.filter(variant__isnull=True),
                to_attr='base_inventory',
            ),
            'images',
        )
        .order_by('-updated_at')
    )


def get_listing_for_management(*, shop, listing_id) -> Listing:
    return (
        Listing.objects.select_related('shop', 'category')
        .prefetch_related('images', 'variants__selected_values__option', 'inventory_rows', 'attributes', 'option_groups__values', 'personalization_fields', 'digital_assets')
        .get(id=listing_id, shop=shop)
    )


def public_listing_detail(*, slug: str) -> Listing:
    return (
        Listing.objects.filter(
            slug=slug,
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
        )
        .exclude(shop__verification_status='suspended')
        .select_related('shop', 'category')
        .prefetch_related('images', 'variants__selected_values__option', 'attributes', 'inventory_rows', 'personalization_fields')
        .get()
    )


def public_listings_for_category(*, category):
    return (
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
        )
        .filter(Q(category=category) | Q(category__parent=category))
        .exclude(shop__verification_status='suspended')
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-published_at', '-created_at')
    )


def public_listings_for_shop(*, shop, section=None, query='', sort='newest', limit: int = 48):
    qs = (
        Listing.objects.filter(
            shop=shop,
            status=ListingStatus.ACTIVE,
        )
        .select_related('category')
        .prefetch_related('images')
        .annotate(
            display_rating=Avg('reviews__rating', filter=Q(reviews__is_visible=True)),
            display_review_count=Count('reviews', filter=Q(reviews__is_visible=True), distinct=True),
        )
        .order_by('-published_at', '-created_at')
    )
    if section is not None:
        qs = qs.filter(section_items__section=section)
    query = ' '.join((query or '').split())[:100]
    if query:
        qs = qs.filter(
            Q(title__icontains=query) | Q(short_description__icontains=query)
            | Q(description__icontains=query) | Q(category__name__icontains=query)
        ).distinct()
    if sort == 'price_asc':
        qs = qs.order_by('base_price', '-published_at')
    elif sort == 'price_desc':
        qs = qs.order_by('-base_price', '-published_at')
    elif sort == 'name':
        qs = qs.order_by('title')
    return qs[:limit]


def visible_root_categories():
    from apps.marketplace.categories.models import Category

    return (
        Category.objects.filter(is_visible=True, parent__isnull=True)
        .prefetch_related('children')
        .order_by('position', 'name')
    )


def get_visible_category(*, slug: str):
    from apps.marketplace.categories.models import Category

    return Category.objects.prefetch_related('children').get(slug=slug, is_visible=True)
