from django.http import Http404
from django.shortcuts import render

from apps.marketplace.content.selectors import public_collection


def collection_detail(request, slug: str):
    from apps.marketplace.content.models import Collection

    try:
        collection = public_collection(slug=slug)
    except Collection.DoesNotExist as exc:
        raise Http404('Collection not found.') from exc
    listings = [
        listing
        for listing in collection.listings.select_related('shop').prefetch_related('images').all()
        if listing.is_publicly_visible
    ]
    return render(
        request,
        'content/collection_detail.html',
        {
            'collection': collection,
            'listings': listings,
            'page_title': collection.name,
        },
    )
