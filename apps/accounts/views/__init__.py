from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.forms import AddressForm, LoginForm, ProfileForm, RegistrationForm
from apps.accounts.models import Address
from apps.accounts.selectors import get_address_for_user, list_addresses_for_user
from apps.accounts.services import (
    create_address,
    delete_address,
    register_user,
    update_address,
    update_user_profile,
)
from apps.accounts.utils import safe_next_url


def register_view(request):
    if request.user.is_authenticated:
        if request.headers.get('HX-Request'):
            from django.http import HttpResponse
            response = HttpResponse()
            response['HX-Redirect'] = reverse('accounts:account_home')
            return response
        return redirect('accounts:account_home')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = register_user(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1'],
                display_name=form.cleaned_data.get('display_name') or '',
                phone=form.cleaned_data.get('phone') or '',
            )
        except ValidationError as exc:
            if hasattr(exc, 'message_dict'):
                for field, errors in exc.message_dict.items():
                    for error in errors:
                        form.add_error(field if field in form.fields else None, error)
            else:
                form.add_error(None, exc)
        else:
            login(request, user)
            messages.success(request, 'Welcome to Ziuza — your account is ready.')
            if request.headers.get('HX-Request'):
                from django.http import HttpResponse
                response = HttpResponse()
                response['HX-Redirect'] = reverse('accounts:account_home')
                return response
            return redirect('accounts:account_home')

    template_name = 'accounts/partials/register_modal.html' if request.headers.get('HX-Request') else 'accounts/register.html'
    return render(request, template_name, {'form': form, 'page_title': 'Create account'})


def login_view(request):
    if request.user.is_authenticated:
        if request.headers.get('HX-Request'):
            from django.http import HttpResponse
            response = HttpResponse()
            response['HX-Redirect'] = reverse('accounts:account_home')
            return response
        return redirect('accounts:account_home')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
        )
        if user is None:
            form.add_error(None, 'Invalid email or password.')
        else:
            login(request, user)
            next_url = safe_next_url(
                request,
                request.POST.get('next') or request.GET.get('next'),
                reverse('accounts:account_home'),
            )
            if request.headers.get('HX-Request'):
                from django.http import HttpResponse
                response = HttpResponse()
                response['HX-Redirect'] = next_url
                return response
            return redirect(next_url)

    template_name = 'accounts/partials/login_modal.html' if request.headers.get('HX-Request') else 'accounts/login.html'
    return render(request, template_name, {'form': form, 'page_title': 'Sign in'})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('core:home')


@login_required
def account_home(request):
    from apps.accounts.selectors import account_summary

    summary = account_summary(user=request.user)
    return render(
        request,
        'accounts/home.html',
        {
            'page_title': 'Your account',
            'account_section': 'home',
            **summary,
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            update_user_profile(
                actor=request.user,
                display_name=form.cleaned_data['display_name'],
                first_name=form.cleaned_data.get('first_name') or '',
                last_name=form.cleaned_data.get('last_name') or '',
                phone=form.cleaned_data.get('phone') or '',
            )
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm.from_user(request.user)

    return render(
        request,
        'accounts/profile.html',
        {
            'form': form,
            'page_title': 'Your profile',
            'account_section': 'profile',
        },
    )


@login_required
def address_list(request):
    addresses = list_addresses_for_user(user=request.user)
    return render(
        request,
        'accounts/address_list.html',
        {
            'addresses': addresses,
            'page_title': 'Addresses',
            'account_section': 'addresses',
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def address_create(request):
    form = AddressForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        create_address(actor=request.user, **form.cleaned_data)
        messages.success(request, 'Address saved.')
        return redirect('accounts:address_list')

    return render(
        request,
        'accounts/address_form.html',
        {
            'form': form,
            'page_title': 'Add address',
            'account_section': 'addresses',
            'form_action': reverse('accounts:address_create'),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def address_edit(request, address_id):
    try:
        address = get_address_for_user(user=request.user, address_id=address_id)
    except Address.DoesNotExist as exc:
        raise Http404('Address not found.') from exc

    form = AddressForm(request.POST or None, instance=address)
    if request.method == 'POST' and form.is_valid():
        try:
            update_address(actor=request.user, address_id=address.id, **form.cleaned_data)
        except PermissionDenied as exc:
            raise Http404('Address not found.') from exc
        messages.success(request, 'Address updated.')
        return redirect('accounts:address_list')

    return render(
        request,
        'accounts/address_form.html',
        {
            'form': form,
            'address': address,
            'page_title': 'Edit address',
            'account_section': 'addresses',
            'form_action': reverse('accounts:address_edit', kwargs={'address_id': address.id}),
        },
    )


@login_required
@require_POST
def address_delete(request, address_id):
    try:
        delete_address(actor=request.user, address_id=address_id)
    except PermissionDenied as exc:
        raise Http404('Address not found.') from exc
    messages.success(request, 'Address deleted.')
    return redirect('accounts:address_list')
