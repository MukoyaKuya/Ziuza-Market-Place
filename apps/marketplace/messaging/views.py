from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.marketplace.listings.models import Listing
from apps.marketplace.messaging.models import Conversation, send_message, start_or_get_conversation
from apps.marketplace.messaging.models import CustomOrderRequest, create_custom_order_request, respond_to_custom_order
from decimal import Decimal, InvalidOperation
from django.utils.dateparse import parse_date
from apps.marketplace.shops.dashboard_context import dashboard_context
from apps.marketplace.shops.models import Shop
from apps.marketplace.shops.selectors import get_shop_for_user
from apps.marketplace.shops.permissions import MANAGE_MESSAGES, ensure_shop_permission, user_has_shop_permission


@login_required
def buyer_inbox(request):
    conversations = (
        Conversation.objects.filter(buyer=request.user)
        .select_related('shop', 'listing')
        .prefetch_related('messages')
    )
    return render(
        request,
        'messaging/buyer_inbox.html',
        {'conversations': conversations, 'page_title': 'Messages', 'account_section': 'messages'},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def conversation_detail(request, conversation_id):
    try:
        conversation = Conversation.objects.select_related('shop', 'listing', 'buyer').get(id=conversation_id)
    except Conversation.DoesNotExist as exc:
        raise Http404 from exc
    if request.user.id != conversation.buyer_id and not user_has_shop_permission(actor=request.user, shop=conversation.shop, permission=MANAGE_MESSAGES):
        raise PermissionDenied
    if request.method == 'POST':
        try:
            send_message(actor=request.user, conversation=conversation, body=request.POST.get('body') or '')
            messages.success(request, 'Message sent.')
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        return redirect('messaging:detail', conversation_id=conversation.id)

    thread = conversation.messages.select_related('sender')
    shop = get_shop_for_user(user=request.user)
    if shop and shop.id == conversation.shop_id:
        return render(
            request,
            'messaging/seller_thread.html',
            dashboard_context(actor=request.user, shop=shop, section='messages', conversation=conversation, thread=thread),
        )
    return render(
        request,
        'messaging/thread.html',
        {
            'conversation': conversation,
            'thread': thread,
            'page_title': conversation.subject or 'Conversation',
            'account_section': 'messages',
        },
    )


@login_required
@require_POST
def start_from_listing(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    try:
        conversation = start_or_get_conversation(
            actor=request.user,
            shop=listing.shop,
            listing=listing,
            subject=f'About {listing.title}',
        )
        body = (request.POST.get('body') or '').strip()
        if body:
            send_message(actor=request.user, conversation=conversation, body=body)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect('listings:detail', slug=listing.slug)
    return redirect('messaging:detail', conversation_id=conversation.id)


@login_required
def seller_inbox(request):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        return redirect('shops:onboarding')
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_MESSAGES)
    conversations = (
        Conversation.objects.filter(shop=shop)
        .select_related('buyer', 'listing')
        .prefetch_related('messages')
    )
    return render(
        request,
        'messaging/seller_inbox.html',
        dashboard_context(actor=request.user, shop=shop, section='messages', conversations=conversations),
    )


@login_required
@require_POST
def request_custom_order(request, listing_id):
    listing = get_object_or_404(Listing.objects.select_related('shop'), id=listing_id)
    try:
        budget = Decimal(request.POST['budget']) if request.POST.get('budget') else None
        custom_request = create_custom_order_request(
            actor=request.user, shop=listing.shop, listing=listing,
            description=request.POST.get('description') or '', budget=budget,
            needed_by=parse_date(request.POST.get('needed_by') or ''),
        )
        messages.success(request, 'Custom-order request sent.')
    except (ValidationError, InvalidOperation) as exc:
        messages.error(request, str(exc))
    return redirect('listings:detail', slug=listing.slug)


@login_required
def seller_custom_orders(request):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        return redirect('shops:onboarding')
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_MESSAGES)
    requests = shop.custom_order_requests.select_related('buyer', 'listing')
    return render(request, 'messaging/custom_orders.html', dashboard_context(actor=request.user, shop=shop, section='custom_orders', custom_requests=requests, statuses=CustomOrderRequest.Status.choices))


@login_required
def buyer_custom_orders(request):
    requests = request.user.custom_order_requests.select_related('shop', 'listing')
    return render(request, 'messaging/buyer_custom_orders.html', {'custom_requests': requests, 'page_title': 'Custom orders', 'account_section': 'messages'})


@login_required
@require_POST
def seller_custom_order_respond(request, request_id):
    shop = get_shop_for_user(user=request.user)
    if shop is None:
        raise Http404
    ensure_shop_permission(actor=request.user, shop=shop, permission=MANAGE_MESSAGES)
    custom_request = get_object_or_404(CustomOrderRequest.objects.select_related('shop', 'buyer'), id=request_id, shop=shop)
    try:
        respond_to_custom_order(actor=request.user, custom_request=custom_request, response=request.POST.get('response') or '', status=request.POST.get('status') or '')
        messages.success(request, 'Response sent.')
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, str(exc))
    return redirect('messaging:seller_custom_orders')
