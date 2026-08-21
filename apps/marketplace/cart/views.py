from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.utils import safe_next_url
from apps.core.htmx import with_toast
from apps.marketplace.cart.services import (
    add_to_cart,
    annotate_cart_totals,
    get_or_create_cart,
    remove_cart_item,
    update_cart_item_quantity,
)
from apps.marketplace.listings.models import Listing, ListingVariant


def cart_page(request):
    cart = get_or_create_cart(request=request)
    context = annotate_cart_totals(cart)
    context['page_title'] = 'Cart'
    return render(request, 'cart/page.html', context)


@require_POST
def cart_add(request):
    listing_id = request.POST.get('listing_id')
    quantity = int(request.POST.get('quantity') or 1)
    personalization_text = request.POST.get('personalization_text', '').strip()
    personalization_data = {
        key.removeprefix('personalization_'): value
        for key, value in request.POST.items()
        if key.startswith('personalization_')
    }
    toast_message = 'Added to cart.'
    toast_type = 'success'
    try:
        listing = Listing.objects.get(id=listing_id)
        variant = None
        if request.POST.get('variant_id'):
            variant = ListingVariant.objects.get(id=request.POST['variant_id'], listing=listing)
        add_to_cart(
            request=request, listing=listing, quantity=quantity, variant=variant,
            personalization_text=personalization_text, personalization_data=personalization_data,
        )
        messages.success(request, toast_message)
    except (Listing.DoesNotExist, ListingVariant.DoesNotExist) as exc:
        raise Http404 from exc
    except (ValidationError, ValueError) as exc:
        toast_message = str(exc)
        toast_type = 'error'
        messages.error(request, toast_message)
    if request.headers.get('HX-Request'):
        cart = get_or_create_cart(request=request)
        response = render(request, 'cart/partials/count.html', annotate_cart_totals(cart))
        return with_toast(response, message=toast_message, type=toast_type)
    return redirect(safe_next_url(request, request.POST.get('next'), 'cart:page'))


@require_POST
def cart_update_quantity(request, item_id):
    try:
        quantity = int(request.POST.get('quantity') or 1)
        update_cart_item_quantity(request=request, item_id=item_id, quantity=quantity)
    except (ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect('cart:page')


@require_POST
def cart_remove(request, item_id):
    remove_cart_item(request=request, item_id=item_id)
    messages.info(request, 'Item removed.')
    return redirect('cart:page')
