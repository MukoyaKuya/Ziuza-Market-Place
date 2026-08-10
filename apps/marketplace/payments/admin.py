from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('provider_reference', 'order', 'provider', 'amount', 'currency', 'status', 'initiated_at', 'confirmed_at')
    list_filter = ('provider', 'status')
    search_fields = ('provider_reference', 'order__public_number')
    raw_id_fields = ('order',)
