from django.urls import path

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
)

app_name = 'accounts'

urlpatterns = [
    path('', account_home, name='account_home'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('addresses/', address_list, name='address_list'),
    path('addresses/new/', address_create, name='address_create'),
    path('addresses/<uuid:address_id>/edit/', address_edit, name='address_edit'),
    path('addresses/<uuid:address_id>/delete/', address_delete, name='address_delete'),
]
