from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.forms import AddressForm, LoginForm, ProfileForm, RegistrationForm
from apps.accounts.models import Address
from apps.accounts.selectors import get_address_for_user, list_addresses_for_user
from apps.accounts.services import (
    create_address,
    delete_address,
    issue_email_otp,
    register_user,
    update_address,
    update_user_profile,
    verify_email_otp,
)
from apps.accounts.utils import email_verification_required, safe_next_url

User = get_user_model()

PENDING_VERIFICATION_SESSION_KEY = 'pending_verification_user_id'
DEBUG_OTP_PREVIEW_SESSION_KEY = 'debug_otp_preview'
POST_AUTH_REDIRECT_SESSION_KEY = 'post_auth_redirect'


def _requested_next_url(request) -> str:
    return safe_next_url(
        request,
        request.POST.get('next') or request.GET.get('next'),
        '',
    )


def _remember_post_auth_redirect(request, next_url: str) -> None:
    if next_url:
        request.session[POST_AUTH_REDIRECT_SESSION_KEY] = next_url
    else:
        request.session.pop(POST_AUTH_REDIRECT_SESSION_KEY, None)


def _redirect_response(request, url: str):
    if request.headers.get('HX-Request'):
        response = HttpResponse()
        response['HX-Redirect'] = url
        return response
    return redirect(url)


def _issue_otp(request, user) -> None:
    """Issue a verification code; keep a DEBUG-only copy so the verify page can show it."""
    code = issue_email_otp(user=user)
    if code is not None and settings.DEBUG:
        request.session[DEBUG_OTP_PREVIEW_SESSION_KEY] = code


def _pending_verification_user(request):
    """User awaiting the OTP gate: session-tracked (signup) or the logged-in unverified user."""
    user_id = request.session.get(PENDING_VERIFICATION_SESSION_KEY)
    if user_id:
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            request.session.pop(PENDING_VERIFICATION_SESSION_KEY, None)
    if request.user.is_authenticated and not request.user.email_verified:
        return request.user
    return None


def register_view(request):
    next_url = _requested_next_url(request)
    if request.user.is_authenticated:
        return _redirect_response(request, next_url or reverse('accounts:account_home'))

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
            if not email_verification_required(user):
                login(request, user)
                messages.success(request, 'Welcome to Ziuza. Your account is ready.')
                return _redirect_response(request, next_url or reverse('accounts:account_home'))
            # Account is created but stays locked behind the email OTP gate:
            # the user is only signed in after entering the code we email them.
            request.session[PENDING_VERIFICATION_SESSION_KEY] = str(user.id)
            _remember_post_auth_redirect(request, next_url)
            _issue_otp(request, user)
            messages.success(request, f'Welcome to Ziuza — enter the 6-digit code we sent to {user.email}.')
            return _redirect_response(request, reverse('accounts:verify_email_otp'))

    template_name = 'accounts/partials/register_modal.html' if request.headers.get('HX-Request') else 'accounts/register.html'
    return render(request, template_name, {'form': form, 'next_url': next_url, 'page_title': 'Create account'})


def login_view(request):
    next_url = _requested_next_url(request)
    if request.user.is_authenticated:
        return _redirect_response(request, next_url or reverse('accounts:account_home'))

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
            if email_verification_required(user):
                request.session[PENDING_VERIFICATION_SESSION_KEY] = str(user.id)
                _remember_post_auth_redirect(request, next_url)
                _issue_otp(request, user)
                messages.info(request, f'Verify your email — we sent a 6-digit code to {user.email}.')
                return _redirect_response(request, reverse('accounts:verify_email_otp'))
            login(request, user)
            return _redirect_response(request, next_url or reverse('accounts:account_home'))

    template_name = 'accounts/partials/login_modal.html' if request.headers.get('HX-Request') else 'accounts/login.html'
    return render(request, template_name, {'form': form, 'next_url': next_url, 'page_title': 'Sign in'})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('core:home')


def verify_email_otp_view(request):
    """Enter the emailed 6-digit code. Signs the user in on success (signup flow)."""
    user = _pending_verification_user(request)
    if user is None or user.email_verified:
        if request.user.is_authenticated:
            return redirect('accounts:account_home')
        return redirect('accounts:login')

    if request.method == 'POST' and verify_email_otp(user=user, code=request.POST.get('code') or ''):
        request.session.pop(PENDING_VERIFICATION_SESSION_KEY, None)
        request.session.pop(DEBUG_OTP_PREVIEW_SESSION_KEY, None)
        redirect_url = safe_next_url(
            request,
            request.session.pop(POST_AUTH_REDIRECT_SESSION_KEY, None),
            reverse('accounts:account_home'),
        )
        if not request.user.is_authenticated:
            login(request, user)
        messages.success(request, 'Email verified — karibu! Your account is ready.')
        return redirect(redirect_url)
    if request.method == 'POST':
        messages.error(request, 'That code is invalid, expired, or out of attempts. Request a new one.')

    return render(
        request,
        'accounts/verify_otp.html',
        {
            'email': user.email,
            'debug_code': request.session.get(DEBUG_OTP_PREVIEW_SESSION_KEY) if settings.DEBUG else None,
            'page_title': 'Verify your email',
        },
    )


@require_POST
def resend_verification(request):
    """Issue a fresh code for the pending (session) or logged-in unverified user."""
    user = _pending_verification_user(request)
    if user is not None and not user.email_verified:
        _issue_otp(request, user)
        messages.info(request, f'A new 6-digit code is on its way to {user.email}.')
    if request.user.is_authenticated:
        return redirect('accounts:verify_email_otp')
    if user is not None:
        return redirect('accounts:verify_email_otp')
    return redirect('accounts:login')


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
