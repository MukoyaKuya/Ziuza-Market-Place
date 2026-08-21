from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.orders.models import OrderItem
from apps.marketplace.reviews.models import (
    Review,
    ReviewMedia,
)
from apps.marketplace.reviews.services import (
    create_review,
    delete_review_media,
    report_review,
    respond_to_review,
    toggle_helpful_vote,
    update_review,
)
from apps.marketplace.shops.selectors import get_shop_for_user


def _review_fields(request):
    return {
        'rating': request.POST.get('rating') or 0,
        'quality_rating': request.POST.get('quality_rating') or 0,
        'shipping_rating': request.POST.get('shipping_rating') or 0,
        'service_rating': request.POST.get('service_rating') or 0,
        'title': request.POST.get('title') or '',
        'body': request.POST.get('body') or '',
        'photos': request.FILES.getlist('photos'),
    }


@login_required
@require_http_methods(['GET', 'POST'])
def create_review_view(request, order_item_id):
    item = get_object_or_404(OrderItem.objects.select_related('order', 'seller_order__shop'), id=order_item_id, order__buyer=request.user)
    existing = Review.objects.filter(order_item=item).first()
    if existing:
        return redirect('reviews:edit', review_id=existing.id)
    if request.method == 'POST':
        try:
            create_review(actor=request.user, order_item=item, **_review_fields(request))
            messages.success(request, 'Verified purchase review submitted.')
            return redirect('orders:buyer_detail', public_number=item.order.public_number)
        except (ValidationError, ValueError) as exc:
            messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
    return render(request, 'reviews/create.html', {'item': item, 'page_title': 'Write a review'})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_review_view(request, review_id):
    review = get_object_or_404(Review.objects.select_related('order_item__order'), id=review_id, buyer=request.user)
    if request.method == 'POST':
        try:
            update_review(actor=request.user, review=review, **_review_fields(request))
            messages.success(request, 'Review updated.')
            return redirect('orders:buyer_detail', public_number=review.order_item.order.public_number)
        except (ValidationError, ValueError) as exc:
            messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
    return render(request, 'reviews/create.html', {
        'item': review.order_item, 'review': review, 'page_title': 'Edit review',
    })


@login_required
@require_POST
def delete_media_view(request, media_id):
    media = get_object_or_404(ReviewMedia.objects.select_related('review'), id=media_id, review__buyer=request.user)
    review_id = media.review_id
    try:
        delete_review_media(actor=request.user, media=media)
        messages.success(request, 'Review photo removed.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('reviews:edit', review_id=review_id)


@login_required
@require_POST
def helpful_vote_view(request, review_id):
    review = get_object_or_404(Review, id=review_id, is_visible=True)
    try:
        helpful = toggle_helpful_vote(actor=request.user, review=review)
        messages.success(request, 'Marked helpful.' if helpful else 'Helpful vote removed.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('listings:detail', slug=review.listing.slug)


@login_required
@require_POST
def report_review_view(request, review_id):
    review = get_object_or_404(Review, id=review_id, is_visible=True)
    try:
        report_review(
            actor=request.user, review=review, reason=request.POST.get('reason') or '',
            details=request.POST.get('details') or '',
        )
        messages.success(request, 'Review reported to Ziuza moderation.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('listings:detail', slug=review.listing.slug)


@login_required
@require_POST
def seller_response_view(request, review_id):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        raise Http404
    review = get_object_or_404(Review, id=review_id, shop=shop)
    try:
        respond_to_review(actor=request.user, review=review, response=request.POST.get('response') or '')
        messages.success(request, 'Public response saved.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('shops:dashboard_reviews')
