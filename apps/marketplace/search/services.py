import re
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher

from django.db.models import Case, F, IntegerField, Prefetch, Q, Value, When

from apps.marketplace.categories.models import Category
from apps.marketplace.listings.models import Inventory, Listing, ListingStatus, ProductType
from apps.marketplace.shops.models import Shop, ShopVerificationStatus


SORT_OPTIONS = {'relevance', 'newest', 'price_asc', 'price_desc', 'rating'}
PRODUCT_TYPES = set(ProductType.values)
STOP_WORDS = {'a', 'an', 'and', 'for', 'in', 'of', 'the', 'to', 'with'}


@dataclass(frozen=True)
class SearchResult:
    listings: object
    used_typo_fallback: bool = False


@dataclass(frozen=True)
class DiscoverySuggestions:
    listings: object
    categories: object
    shops: object


def normalize_query(query: str) -> str:
    return ' '.join((query or '').strip().split())[:100]


def _terms(query: str) -> list[str]:
    terms = [term.casefold() for term in re.findall(r"[\w'-]+", query, flags=re.UNICODE)]
    useful = [term for term in terms if term not in STOP_WORDS]
    return (useful or terms)[:8]


def _base_listings(
    *,
    category_slug: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    shop_slug: str | None = None,
    product_type: str | None = None,
    county: str | None = None,
    verified_only: bool = False,
    personalizable_only: bool = False,
    in_stock_only: bool = False,
):
    base_inventory = Inventory.objects.filter(variant__isnull=True)
    qs = (
        Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            shop__is_active=True,
            shop__vacation_mode=False,
        )
        .exclude(shop__verification_status=ShopVerificationStatus.SUSPENDED)
        .select_related('shop', 'category')
        .prefetch_related('images', Prefetch('inventory_rows', queryset=base_inventory, to_attr='search_base_inventory'))
    )
    if category_slug:
        qs = qs.filter(Q(category__slug=category_slug) | Q(category__parent__slug=category_slug))
    if min_price is not None:
        qs = qs.filter(base_price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(base_price__lte=max_price)
    if shop_slug:
        qs = qs.filter(shop__slug=shop_slug)
    if product_type in PRODUCT_TYPES:
        qs = qs.filter(product_type=product_type)
    if county:
        qs = qs.filter(shop__county__iexact=county[:100])
    if verified_only:
        qs = qs.filter(shop__verification_status=ShopVerificationStatus.VERIFIED)
    if personalizable_only:
        qs = qs.filter(is_personalizable=True)
    if in_stock_only:
        qs = qs.filter(
            Q(product_type=ProductType.DIGITAL)
            | Q(
                inventory_rows__variant__isnull=True,
                inventory_rows__quantity_available__gt=F('inventory_rows__quantity_reserved'),
            )
        ).distinct()
    return qs


def _text_filter(query: str) -> Q:
    combined = Q()
    for term in _terms(query):
        combined &= (
            Q(title__icontains=term)
            | Q(short_description__icontains=term)
            | Q(description__icontains=term)
            | Q(shop__name__icontains=term)
            | Q(category__name__icontains=term)
            | Q(attributes__value__icontains=term)
        )
    return combined


def _relevance_expression(query: str):
    score = Case(
        When(title__iexact=query, then=Value(160)),
        When(title__istartswith=query, then=Value(120)),
        When(title__icontains=query, then=Value(90)),
        When(category__name__iexact=query, then=Value(75)),
        When(shop__name__iexact=query, then=Value(70)),
        When(short_description__icontains=query, then=Value(45)),
        When(description__icontains=query, then=Value(20)),
        default=Value(0),
        output_field=IntegerField(),
    )
    for term in _terms(query):
        score += Case(
            When(title__iexact=term, then=Value(45)),
            When(title__istartswith=term, then=Value(35)),
            When(title__icontains=term, then=Value(28)),
            When(category__name__icontains=term, then=Value(20)),
            When(shop__name__icontains=term, then=Value(18)),
            When(short_description__icontains=term, then=Value(12)),
            When(attributes__value__icontains=term, then=Value(10)),
            default=Value(4),
            output_field=IntegerField(),
        )
    return score


def _rank_and_sort(qs, *, query: str, sort: str):
    quality = Case(
        When(is_featured=True, shop__verification_status=ShopVerificationStatus.VERIFIED, then=Value(25)),
        When(is_featured=True, then=Value(15)),
        When(shop__verification_status=ShopVerificationStatus.VERIFIED, then=Value(10)),
        default=Value(0),
        output_field=IntegerField(),
    )
    qs = qs.annotate(merchandising_score=quality)
    if query:
        qs = qs.annotate(relevance_score=_relevance_expression(query))
    else:
        qs = qs.annotate(relevance_score=Value(0, output_field=IntegerField()))
    if sort == 'price_asc':
        return qs.order_by('base_price', '-relevance_score', '-published_at')
    if sort == 'price_desc':
        return qs.order_by('-base_price', '-relevance_score', '-published_at')
    if sort == 'newest':
        return qs.order_by('-published_at', '-created_at')
    if sort == 'rating':
        return qs.order_by('-shop__rating_average', '-shop__rating_count', '-relevance_score', '-published_at')
    return qs.order_by(
        '-relevance_score', '-merchandising_score', '-shop__rating_average',
        '-shop__rating_count', '-published_at', '-created_at',
    )


def search_listings(
    *,
    query: str = '',
    category_slug: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    shop_slug: str | None = None,
    sort: str = 'relevance',
    product_type: str | None = None,
    county: str | None = None,
    verified_only: bool = False,
    personalizable_only: bool = False,
    in_stock_only: bool = False,
):
    """Rank public marketplace listings using text relevance and trusted merchandising signals."""
    query = normalize_query(query)
    sort = sort if sort in SORT_OPTIONS else 'relevance'
    qs = _base_listings(
        category_slug=category_slug,
        min_price=min_price,
        max_price=max_price,
        shop_slug=shop_slug,
        product_type=product_type,
        county=county,
        verified_only=verified_only,
        personalizable_only=personalizable_only,
        in_stock_only=in_stock_only,
    )
    if query:
        qs = qs.filter(_text_filter(query)).distinct()
    return _rank_and_sort(qs, query=query, sort=sort)


def _word_similarity(query_terms: list[str], text: str) -> float:
    words = _terms(text)
    if not words:
        return 0.0
    per_term = []
    for term in query_terms:
        best = max(SequenceMatcher(None, term, word).ratio() for word in words)
        threshold = 0.74 if len(term) >= 5 else 0.80
        if best < threshold:
            return 0.0
        per_term.append(best)
    return sum(per_term) / len(per_term)


def search_with_fallback(**filters) -> SearchResult:
    query = normalize_query(filters.get('query', ''))
    filters['query'] = query
    direct = search_listings(**filters)
    if not query or direct.exists():
        return SearchResult(direct)

    base_filters = dict(filters)
    base_filters['query'] = ''
    candidates = search_listings(**base_filters)[:400]
    query_terms = _terms(query)
    scored = []
    for listing in candidates:
        searchable = ' '.join((listing.title, listing.category.name, listing.shop.name))
        similarity = _word_similarity(query_terms, searchable)
        if similarity:
            scored.append((similarity, listing.pk))
    scored.sort(key=lambda item: item[0], reverse=True)
    ids = [pk for _score, pk in scored[:100]]
    if not ids:
        return SearchResult(direct)
    preserved_order = Case(
        *[When(pk=pk, then=position) for position, pk in enumerate(ids)],
        output_field=IntegerField(),
    )
    fuzzy = _base_listings(
        category_slug=filters.get('category_slug'),
        min_price=filters.get('min_price'),
        max_price=filters.get('max_price'),
        shop_slug=filters.get('shop_slug'),
        product_type=filters.get('product_type'),
        county=filters.get('county'),
        verified_only=filters.get('verified_only', False),
        personalizable_only=filters.get('personalizable_only', False),
        in_stock_only=filters.get('in_stock_only', False),
    ).filter(pk__in=ids)
    sort = filters.get('sort', 'relevance')
    if sort == 'price_asc':
        fuzzy = fuzzy.order_by('base_price', preserved_order)
    elif sort == 'price_desc':
        fuzzy = fuzzy.order_by('-base_price', preserved_order)
    elif sort == 'newest':
        fuzzy = fuzzy.order_by('-published_at', '-created_at')
    elif sort == 'rating':
        fuzzy = fuzzy.order_by('-shop__rating_average', '-shop__rating_count', preserved_order)
    else:
        fuzzy = fuzzy.order_by(preserved_order)
    return SearchResult(fuzzy, used_typo_fallback=True)


def suggest_discovery(*, query: str, limit: int = 6) -> DiscoverySuggestions:
    query = normalize_query(query)
    if len(query) < 2:
        return DiscoverySuggestions(Listing.objects.none(), Category.objects.none(), Shop.objects.none())
    result = search_with_fallback(query=query)
    categories = Category.objects.filter(is_visible=True, name__icontains=query).order_by('position', 'name')[:3]
    shops = (
        Shop.objects.filter(is_active=True, vacation_mode=False, name__icontains=query)
        .exclude(verification_status=ShopVerificationStatus.SUSPENDED)
        .order_by('-rating_average', 'name')[:3]
    )
    return DiscoverySuggestions(result.listings[:limit], categories, shops)


def suggest_listings(*, query: str, limit: int = 8):
    return suggest_discovery(query=query, limit=limit).listings
