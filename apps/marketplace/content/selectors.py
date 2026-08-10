from django.utils import timezone
from django.db.models import Count, Prefetch, Q

from apps.marketplace.categories.models import Category
from apps.marketplace.content.models import Collection, HeroSlide, HomepageSection
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.shops.models import Shop, ShopVerificationStatus


def live_homepage_sections(*, now=None):
    now = now or timezone.now()
    sections = HomepageSection.objects.filter(is_visible=True).order_by('position')
    return [section for section in sections if section.is_live(now=now)]


def live_hero_slides(*, now=None, limit: int = 5):
    now = now or timezone.now()
    slides = HeroSlide.objects.order_by('priority', '-updated_at')
    return [slide for slide in slides if slide.is_live(now=now)][:limit]


def live_collections(*, now=None, limit: int = 8):
    now = now or timezone.now()
    collections = Collection.objects.prefetch_related('listings').order_by('name')
    return [c for c in collections if c.is_live(now=now)][:limit]


def featured_listings(*, limit: int = 8):
    return (
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            is_featured=True,
            shop__is_active=True,
        )
        .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-published_at')[:limit]
    )


def rotating_discovery(*, position: int, limit: int = 8):
    """Return the next visible category that has public listings and its products."""
    categories = list(Category.objects.filter(is_visible=True, parent__isnull=True).order_by('position', 'name'))
    if not categories:
        return None, []

    for offset in range(len(categories)):
        category = categories[(position + offset) % len(categories)]
        listings = list(
            Listing.objects.filter(
                status=ListingStatus.ACTIVE,
                shop__is_active=True,
            )
            .filter(category__in=[category, *category.children.filter(is_visible=True)])
            .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
            .select_related('shop', 'category')
            .prefetch_related('images')
            .order_by('-published_at', '-created_at')[:limit]
        )
        if listings:
            return category, listings

    return None, []


def homepage_discovery(*, position: int, limit: int = 4):
    """Build a full discovery row while keeping its lead category meaningful."""
    category, listings = rotating_discovery(position=position, limit=limit)
    if not category:
        return None, list(featured_listings(limit=limit)), False

    if len(listings) >= limit:
        return category, listings, False

    listing_ids = [listing.id for listing in listings]
    fillers = list(
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
        )
        .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
        .exclude(id__in=listing_ids)
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-is_featured', '-published_at', '-created_at')[: limit - len(listings)]
    )
    return category, [*listings, *fillers], bool(fillers)


def featured_shops(*, limit: int = 6):
    spotlight_listings = (
        Listing.objects.filter(status=ListingStatus.ACTIVE)
        .prefetch_related('images')
        .order_by('-is_featured', '-published_at')[:3]
    )
    return (
        Shop.objects.filter(
            is_active=True,
            verification_status=ShopVerificationStatus.VERIFIED,
            vacation_mode=False,
            listings__status=ListingStatus.ACTIVE,
        )
        .annotate(
            product_count=Count('listings', filter=Q(listings__status=ListingStatus.ACTIVE), distinct=True),
            follower_total=Count('followers', distinct=True),
            visible_review_count=Count('reviews', filter=Q(reviews__is_visible=True), distinct=True),
        )
        .prefetch_related(Prefetch('listings', queryset=spotlight_listings, to_attr='spotlight_listings'))
        .order_by('-rating_average', '-visible_review_count', '-follower_total', '-product_count', 'name')
        .distinct()[:limit]
    )


def public_collection(*, slug: str, now=None) -> Collection:
    now = now or timezone.now()
    collection = Collection.objects.prefetch_related('listings__images', 'listings__shop').get(slug=slug)
    if not collection.is_live(now=now):
        raise Collection.DoesNotExist
    return collection
