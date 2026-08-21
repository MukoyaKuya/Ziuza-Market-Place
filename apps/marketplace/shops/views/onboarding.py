"""Shop onboarding and team invitation acceptance views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.marketplace.shops.forms import CreateShopForm
from apps.marketplace.shops.selectors import get_shop_for_user
from apps.marketplace.shops.services import create_shop
from apps.marketplace.shops.team_services import accept_team_invitation, invitation_for_token


@login_required
def sell_entry(request):
    """/sell/ — dashboard if shop exists, else onboarding."""
    if get_shop_for_user(user=request.user) is not None:
        return redirect('shops:dashboard')
    return redirect('shops:onboarding')


@login_required
@require_http_methods(['GET', 'POST'])
def shop_onboarding(request):
    if get_shop_for_user(user=request.user) is not None:
        return redirect('shops:dashboard')

    form = CreateShopForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            shop = create_shop(
                actor=request.user,
                name=form.cleaned_data['name'],
                description=form.cleaned_data.get('description') or '',
                county=form.cleaned_data['county'],
                sub_county=form.cleaned_data.get('sub_county') or '',
                ward=form.cleaned_data.get('ward') or '',
                location_text=form.cleaned_data.get('location_text') or '',
                is_local_seller=form.cleaned_data.get('is_local_seller', True),
                local_delivery_scope=form.cleaned_data.get('local_delivery_scope') or 'county',
                local_pickup_available=form.cleaned_data.get('local_pickup_available', True),
                local_pickup_instructions=form.cleaned_data.get('local_pickup_instructions') or '',
            )
        except ValidationError as exc:
            if hasattr(exc, 'message_dict'):
                for field, errors in exc.message_dict.items():
                    for error in errors:
                        form.add_error(field if field in form.fields else None, error)
            else:
                form.add_error(None, exc)
        else:
            messages.success(request, f'“{shop.name}” is ready. Welcome to your seller dashboard.')
            return redirect('shops:dashboard')

    return render(
        request,
        'shops/onboarding.html',
        {'form': form, 'page_title': 'Open your shop'},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def accept_team(request, token):
    try:
        invitation = invitation_for_token(actor=request.user, token=token)
        if request.method == 'POST':
            accept_team_invitation(actor=request.user, token=token)
            messages.success(request, f'You joined {invitation.shop.name}.')
            return redirect('shops:dashboard')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('accounts:account_home')
    return render(request, 'shops/team_accept.html', {
        'invitation': invitation,
        'token': token,
        'page_title': f'Join {invitation.shop.name}',
    })
