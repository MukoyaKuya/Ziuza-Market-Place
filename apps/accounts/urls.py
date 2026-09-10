from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from apps.accounts.views import (
    account_home,
    address_create,
    address_delete,
    address_edit,
    address_list,
    login_view,
    logout_view,
    profile_view,
    register_view,
    resend_verification,
    verify_email_otp_view,
)

app_name = 'accounts'

urlpatterns = [
    path('', account_home, name='account_home'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('verify/', verify_email_otp_view, name='verify_email_otp'),
    path('verify/resend/', resend_verification, name='resend_verification'),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url=reverse_lazy('accounts:password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('addresses/', address_list, name='address_list'),
    path('addresses/new/', address_create, name='address_create'),
    path('addresses/<uuid:address_id>/edit/', address_edit, name='address_edit'),
    path('addresses/<uuid:address_id>/delete/', address_delete, name='address_delete'),
]
