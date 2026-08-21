from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import Address, User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ('email', 'display_name', 'phone', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('display_name', 'first_name', 'last_name', 'phone')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'display_name'),
        }),
    )
    search_fields = ('email', 'display_name', 'phone')
    ordering = ('-date_joined',)


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ('recipient_name', 'user', 'city_or_town', 'county', 'is_default_shipping', 'is_default_billing')
    list_filter = ('county', 'country', 'is_default_shipping', 'is_default_billing')
    search_fields = ('recipient_name', 'user__email', 'address_line_1', 'city_or_town')

