from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.marketplace.orders.models import (
    CaseResolutionOutcome,
    DownloadGrant,
    HelpRequest,
    Order,
    OrderItem,
    ProtectionCaseEvent,
    ProtectionCaseEvidence,
    ProtectionCaseMessage,
    SellerOrder,
)
from apps.marketplace.orders.support import resolve_protection_case


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ('shop',)


class SellerOrderInline(TabularInline):
    model = SellerOrder
    extra = 0
    raw_id_fields = ('shop',)


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ('public_number', 'buyer', 'grand_total', 'payment_status', 'fulfillment_status', 'created_at')
    list_filter = ('payment_status', 'fulfillment_status', 'currency')
    search_fields = ('public_number', 'buyer__email', 'promotion_code')
    inlines = [SellerOrderInline, OrderItemInline]
    raw_id_fields = ('buyer',)


@admin.register(SellerOrder)
class SellerOrderAdmin(ModelAdmin):
    list_display = ('order', 'shop', 'subtotal', 'fulfillment_status', 'created_at')
    list_filter = ('fulfillment_status',)
    search_fields = ('order__public_number', 'shop__name')
    raw_id_fields = ('order', 'shop')


@admin.register(HelpRequest)
class HelpRequestAdmin(ModelAdmin):
    list_display = ('order', 'case_type', 'reason', 'status', 'response_due_at', 'escalated_at', 'created_at')
    list_filter = ('status', 'case_type', 'reason', 'resolution_outcome')
    search_fields = ('order__public_number', 'buyer__email', 'description')
    raw_id_fields = ('order', 'seller_order', 'buyer')
    readonly_fields = ('created_at', 'updated_at', 'first_seller_response_at', 'escalated_at', 'resolved_at', 'closed_at')
    actions = ('resolve_for_buyer', 'resolve_for_seller', 'resolve_as_agreement', 'close_without_action')

    def _resolve(self, request, queryset, outcome, note):
        for case in queryset.filter(status__in=['open', 'seller_responded', 'escalated']):
            resolve_protection_case(actor=request.user, case=case, outcome=outcome, notes=note)

    @admin.action(description='Resolve selected cases for buyer')
    def resolve_for_buyer(self, request, queryset):
        self._resolve(request, queryset, CaseResolutionOutcome.BUYER, 'Ziuza reviewed the case and resolved it for the buyer.')

    @admin.action(description='Resolve selected cases for seller')
    def resolve_for_seller(self, request, queryset):
        self._resolve(request, queryset, CaseResolutionOutcome.SELLER, 'Ziuza reviewed the case and resolved it for the seller.')

    @admin.action(description='Record buyer and seller agreement')
    def resolve_as_agreement(self, request, queryset):
        self._resolve(request, queryset, CaseResolutionOutcome.AGREEMENT, 'Ziuza recorded the resolution agreed by the buyer and seller.')

    @admin.action(description='Close selected cases without action')
    def close_without_action(self, request, queryset):
        self._resolve(request, queryset, CaseResolutionOutcome.NO_ACTION, 'Ziuza reviewed and closed the case without further action.')


@admin.register(ProtectionCaseMessage)
class ProtectionCaseMessageAdmin(ModelAdmin):
    list_display = ('case', 'author', 'is_internal', 'created_at')
    list_filter = ('is_internal', 'created_at')
    search_fields = ('case__order__public_number', 'author__email', 'body')
    raw_id_fields = ('case', 'author')


@admin.register(ProtectionCaseEvidence)
class ProtectionCaseEvidenceAdmin(ModelAdmin):
    list_display = ('original_name', 'case', 'uploaded_by', 'content_type', 'size', 'created_at')
    search_fields = ('original_name', 'case__order__public_number', 'uploaded_by__email')
    raw_id_fields = ('case', 'uploaded_by')
    readonly_fields = ('original_name', 'content_type', 'size', 'created_at')


@admin.register(ProtectionCaseEvent)
class ProtectionCaseEventAdmin(ModelAdmin):
    list_display = ('action', 'case', 'actor', 'is_internal', 'created_at')
    list_filter = ('action', 'is_internal', 'created_at')
    search_fields = ('case__order__public_number', 'actor__email', 'note')
    readonly_fields = ('case', 'actor', 'action', 'note', 'is_internal', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DownloadGrant)
class DownloadGrantAdmin(ModelAdmin):
    list_display = ('order_item', 'buyer', 'download_count', 'is_active', 'granted_at')
    list_filter = ('is_active',)
    search_fields = ('buyer__email', 'order_item__order__public_number', 'order_item__title_snapshot')
    raw_id_fields = ('order_item', 'buyer')
