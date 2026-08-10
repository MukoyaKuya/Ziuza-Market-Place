import hashlib
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.db import transaction
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.utils import timezone

from apps.accounts.permissions import ensure_authenticated
from apps.marketplace.listings.models import Listing, ListingStatus
from apps.marketplace.notifications.services import notify
from apps.marketplace.search.models import RecentlyViewedListing, SavedSearch
from apps.marketplace.search.services import PRODUCT_TYPES, SORT_OPTIONS, normalize_query, search_listings
from apps.marketplace.shops.models import ShopVerificationStatus


BOOLEAN_FILTERS = ('verified_only', 'personalizable_only', 'in_stock_only')
TEXT_FILTERS = ('category_slug', 'shop_slug', 'product_type', 'county', 'sort')


def _decimal_string(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return str(parsed.quantize(Decimal('0.01')))


def normalize_saved_criteria(data) -> dict:
    criteria = {'query': normalize_query(data.get('query') or data.get('q') or '')}
    aliases = {
        'category_slug': 'category',
        'shop_slug': 'shop',
        'product_type': 'product_type',
        'county': 'county',
        'sort': 'sort',
    }
    for key in TEXT_FILTERS:
        value = (data.get(key) or data.get(aliases[key]) or '').strip()
        if value:
            criteria[key] = value[:140]
    if criteria.get('product_type') not in PRODUCT_TYPES:
        criteria.pop('product_type', None)
    if criteria.get('sort') not in SORT_OPTIONS:
        criteria['sort'] = 'relevance'
    for key, request_key in (('min_price', 'min_price'), ('max_price', 'max_price')):
        value = _decimal_string(data.get(request_key))
        if value is not None:
            criteria[key] = value
    if 'min_price' in criteria and 'max_price' in criteria and Decimal(criteria['min_price']) > Decimal(criteria['max_price']):
        criteria['min_price'], criteria['max_price'] = criteria['max_price'], criteria['min_price']
    boolean_aliases = {
        'verified_only': 'verified',
        'personalizable_only': 'personalizable',
        'in_stock_only': 'in_stock',
    }
    for key in BOOLEAN_FILTERS:
        raw = data.get(key, data.get(boolean_aliases[key]))
        if raw in (True, '1', 'true', 'on'):
            criteria[key] = True
    return criteria


def _fingerprint(criteria: dict) -> str:
    payload = json.dumps(criteria, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _default_name(criteria: dict) -> str:
    query = criteria.get('query') or 'Marketplace picks'
    category = criteria.get('category_slug')
    return f'{query} · {category}'[:120] if category else query[:120]


def save_search(*, actor, data, name: str = '', alerts_enabled: bool = True) -> tuple[SavedSearch, bool]:
    ensure_authenticated(actor=actor)
    criteria = normalize_saved_criteria(data)
    fingerprint = _fingerprint(criteria)
    saved, created = SavedSearch.objects.update_or_create(
        user=actor,
        fingerprint=fingerprint,
        defaults={
            'name': (name or _default_name(criteria)).strip()[:120],
            'query': criteria.get('query', ''),
            'filters': {key: value for key, value in criteria.items() if key != 'query'},
            'alerts_enabled': alerts_enabled,
        },
    )
    return saved, created


def saved_search_url(saved: SavedSearch) -> str:
    params = {'q': saved.query, **saved.filters}
    aliases = {
        'category_slug': 'category', 'shop_slug': 'shop', 'verified_only': 'verified',
        'personalizable_only': 'personalizable', 'in_stock_only': 'in_stock',
    }
    public = {aliases.get(key, key): ('1' if value is True else value) for key, value in params.items() if value not in ('', None, False)}
    return f'/search/?{urlencode(public)}'


@transaction.atomic
def record_recent_view(*, actor, listing):
    ensure_authenticated(actor=actor)
    recent, created = RecentlyViewedListing.objects.select_for_update().get_or_create(
        user=actor,
        listing=listing,
    )
    if not created:
        recent.view_count = F('view_count') + 1
        recent.save(update_fields=['view_count', 'last_viewed_at'])
        recent.refresh_from_db(fields=['view_count', 'last_viewed_at'])
    return recent


def recent_listings_for_user(*, user, limit: int = 8):
    return (
        Listing.objects.filter(
            recent_views__user=user,
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
            shop__vacation_mode=False,
        )
        .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
        .select_related('shop', 'category')
        .prefetch_related('images')
        .order_by('-recent_views__last_viewed_at')[:limit]
    )


def recommendations_for_user(*, user, limit: int = 8):
    favorite_categories = list(
        user.favorites.values('listing__category_id').annotate(weight=Count('id')).order_by('-weight')[:5]
    )
    recent_categories = list(
        user.recently_viewed_listings.values('listing__category_id').annotate(weight=Count('id')).order_by('-weight')[:5]
    )
    category_scores = {}
    followed_shop_ids = list(user.followed_shops.values_list('shop_id', flat=True)[:50])
    for row in favorite_categories:
        category_scores[row['listing__category_id']] = category_scores.get(row['listing__category_id'], 0) + row['weight'] * 3
    for row in recent_categories:
        category_scores[row['listing__category_id']] = category_scores.get(row['listing__category_id'], 0) + row['weight']

    qs = (
        Listing.objects.filter(status=ListingStatus.ACTIVE, shop__is_active=True, shop__vacation_mode=False)
        .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
        .exclude(shop__owner=user)
        .exclude(favorited_by__user=user)
        .select_related('shop', 'category')
        .prefetch_related('images')
    )
    if category_scores:
        category_rank = Case(
            *[When(category_id=category_id, then=Value(score)) for category_id, score in category_scores.items()],
            default=Value(0),
            output_field=IntegerField(),
        )
        followed_rank = Case(
            When(shop_id__in=followed_shop_ids, then=Value(50)),
            default=Value(0), output_field=IntegerField(),
        )
        qs = qs.filter(Q(category_id__in=category_scores) | Q(shop_id__in=followed_shop_ids)).annotate(
            preference_score=category_rank + followed_rank
        ).order_by(
            '-preference_score', '-is_featured', '-shop__rating_average', '-published_at'
        )
    elif followed_shop_ids:
        qs = qs.filter(shop_id__in=followed_shop_ids).order_by('-published_at', '-created_at')
    else:
        qs = qs.order_by('-is_featured', '-shop__rating_average', '-published_at')
    return qs.distinct()[:limit]


def process_saved_search_alerts(*, limit: int = 500) -> int:
    now = timezone.now()
    notified = 0
    saved_ids = list(SavedSearch.objects.filter(alerts_enabled=True).values_list('id', flat=True)[:limit])
    for saved_id in saved_ids:
        with transaction.atomic():
            saved = SavedSearch.objects.select_for_update().select_related('user').get(id=saved_id)
            criteria = {'query': saved.query, **saved.filters}
            if 'min_price' in criteria:
                criteria['min_price'] = Decimal(criteria['min_price'])
            if 'max_price' in criteria:
                criteria['max_price'] = Decimal(criteria['max_price'])
            matches = list(search_listings(**criteria).filter(published_at__gt=saved.last_checked_at)[:5])
            saved.last_checked_at = now
            update_fields = ['last_checked_at', 'updated_at']
            if matches:
                count = len(matches)
                notify(
                    recipient=saved.user,
                    type='saved_search_match',
                    title=f'New match for {saved.name}',
                    body=f'{count} new listing{"s" if count != 1 else ""} match your saved search.',
                    target_url=saved_search_url(saved),
                )
                saved.last_notified_at = now
                update_fields.append('last_notified_at')
                notified += 1
            saved.save(update_fields=update_fields)
    return notified
