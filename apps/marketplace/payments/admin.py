from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.marketplace.payments.models import Payment, PaymentCallbackEvent


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('provider_reference', 'order', 'provider', 'amount', 'currency', 'status', 'initiated_at', 'confirmed_at')
    list_filter = ('provider', 'status')
    search_fields = ('provider_reference', 'order__public_number')
    raw_id_fields = ('order',)


@admin.register(PaymentCallbackEvent)
class PaymentCallbackEventAdmin(ModelAdmin):
    list_display = ('provider_reference', 'provider', 'outcome', 'authenticated', 'received_at', 'processed_at')
    list_filter = ('provider', 'outcome', 'authenticated')
    search_fields = ('provider_reference', 'payment__provider_reference', 'payment__order__public_number')
    raw_id_fields = ('payment',)
    readonly_fields = (
        'payment',
        'provider',
        'provider_reference',
        'authenticated',
        'payload',
        'outcome',
        'error_code',
        'received_at',
        'processed_at',
    )
