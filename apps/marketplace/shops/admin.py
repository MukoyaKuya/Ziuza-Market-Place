from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.marketplace.shops.models import (
    MarketplaceReport, ModerationAction, Shop, ShopAuditEvent, ShopInvitation,
    ShopMembership, ShopSection, ShopSectionItem, VerificationApplication,
    VerificationApplicationStatus,
)
from apps.marketplace.shops.trust_services import moderate_report, review_verification


@admin.register(Shop)
class ShopAdmin(ModelAdmin):
    list_display = (
        'name',
        'owner',
        'county',
        'verification_status',
        'is_promoted',
        'gift_approval_status',
        'rating_average',
        'is_active',
        'created_at',
    )
    list_filter = ('is_promoted', 'gift_approval_status', 'verification_status', 'vacation_mode', 'is_active', 'county')
    list_editable = ('is_promoted', 'gift_approval_status')
    search_fields = ('name', 'slug', 'owner__email', 'county')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('verification_status', 'rating_average', 'rating_count', 'created_at', 'updated_at')
    raw_id_fields = ('owner',)


@admin.register(VerificationApplication)
class VerificationApplicationAdmin(ModelAdmin):
    change_list_template = 'admin/shops/verificationapplication/change_list.html'
    change_form_template = 'admin/shops/verificationapplication/change_form.html'
    review_template = 'admin/shops/verificationapplication/review.html'
    list_display = ('shop', 'legal_name', 'identity_type', 'identity_last4', 'status_badge', 'submitted_at', 'reviewed_by')
    list_filter = ('status', 'identity_type')
    search_fields = ('shop__name', 'shop__owner__email', 'legal_name', 'business_registration_number')
    readonly_fields = (
        'shop', 'legal_name', 'identity_type', 'identity_last4',
        'business_registration_number', 'contact_phone', 'consent_confirmed',
        'status', 'reviewer_notes', 'submitted_at', 'reviewed_at', 'reviewed_by',
    )
    fieldsets = (
        ('Application', {'fields': ('shop', 'status', 'submitted_at')}),
        ('Identity information', {'fields': ('legal_name', 'identity_type', 'identity_last4', 'business_registration_number')}),
        ('Contact and consent', {'fields': ('contact_phone', 'consent_confirmed')}),
        ('Review record', {'fields': ('reviewer_notes', 'reviewed_by', 'reviewed_at')}),
    )
    actions = ('approve_selected', 'reject_selected')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop', 'shop__owner', 'reviewed_by')

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        tones = {
            VerificationApplicationStatus.PENDING: ('#fff7d6', '#854d0e'),
            VerificationApplicationStatus.APPROVED: ('#e8f7ee', '#166534'),
            VerificationApplicationStatus.REJECTED: ('#feeceb', '#991b1b'),
        }
        background, color = tones[obj.status]
        return format_html(
            '<span style="display:inline-flex;border-radius:999px;padding:4px 10px;font-weight:700;background:{};color:{}">{}</span>',
            background, color, obj.get_status_display(),
        )

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/review/',
                self.admin_site.admin_view(self.review_application_view),
                name='shops_verificationapplication_review',
            ),
        ]
        return custom_urls + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        applications = self.get_queryset(request)
        pending = applications.filter(status=VerificationApplicationStatus.PENDING)
        extra_context = {
            **(extra_context or {}),
            'pending_verification_count': pending.count(),
            'approved_verification_count': applications.filter(status=VerificationApplicationStatus.APPROVED).count(),
            'rejected_verification_count': applications.filter(status=VerificationApplicationStatus.REJECTED).count(),
            'next_pending_application': pending.order_by('submitted_at').first(),
        }
        return super().changelist_view(request, extra_context=extra_context)

    def review_application_view(self, request, object_id):
        application = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_change_permission(request, application):
            return self.admin_site.login(request)
        if request.method == 'POST':
            decision = request.POST.get('decision')
            notes = request.POST.get('notes') or ''
            if decision not in {'approve', 'reject'}:
                messages.error(request, 'Choose approve or reject.')
            else:
                try:
                    review_verification(
                        actor=request.user,
                        application=application,
                        approved=decision == 'approve',
                        notes=notes,
                    )
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                else:
                    messages.success(
                        request,
                        f'{application.shop.name} verification {"approved" if decision == "approve" else "rejected"}.',
                    )
                    return redirect('admin:shops_verificationapplication_changelist')
        context = {
            **self.admin_site.each_context(request),
            'title': f'Review {application.shop.name}',
            'opts': self.model._meta,
            'application': application,
            'changelist_url': reverse('admin:shops_verificationapplication_changelist'),
        }
        return TemplateResponse(request, self.review_template, context)

    @admin.action(description='Approve selected verification applications')
    def approve_selected(self, request, queryset):
        reviewed = 0
        for application in queryset.filter(status=VerificationApplicationStatus.PENDING):
            review_verification(actor=request.user, application=application, approved=True)
            reviewed += 1
        self.message_user(request, f'Approved {reviewed} verification application(s).', messages.SUCCESS)

    @admin.action(description='Reject selected verification applications')
    def reject_selected(self, request, queryset):
        reviewed = 0
        for application in queryset.filter(status=VerificationApplicationStatus.PENDING):
            review_verification(actor=request.user, application=application, approved=False, notes='Application rejected after review.')
            reviewed += 1
        self.message_user(request, f'Rejected {reviewed} verification application(s).', messages.WARNING)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MarketplaceReport)
class MarketplaceReportAdmin(ModelAdmin):
    list_display = ('id', 'reason', 'shop', 'listing', 'reporter', 'status', 'created_at')
    list_filter = ('status', 'reason')
    search_fields = ('details', 'shop__name', 'listing__title', 'reporter__email')
    readonly_fields = ('reporter', 'shop', 'listing', 'reason', 'details', 'created_at')
    actions = ('hide_reported_listing', 'suspend_reported_shop', 'dismiss_selected')

    @admin.action(description='Hide listing and action report')
    def hide_reported_listing(self, request, queryset):
        for report in queryset.filter(listing__isnull=False):
            moderate_report(actor=request.user, report=report, action=ModerationAction.Action.HIDE_LISTING)

    @admin.action(description='Suspend shop and action report')
    def suspend_reported_shop(self, request, queryset):
        for report in queryset:
            moderate_report(actor=request.user, report=report, action=ModerationAction.Action.SUSPEND_SHOP)

    @admin.action(description='Dismiss selected reports')
    def dismiss_selected(self, request, queryset):
        for report in queryset:
            moderate_report(actor=request.user, report=report, action=ModerationAction.Action.DISMISS_REPORT)


@admin.register(ModerationAction)
class ModerationActionAdmin(ModelAdmin):
    list_display = ('action', 'shop', 'listing', 'actor', 'created_at')
    list_filter = ('action',)
    search_fields = ('notes', 'shop__name', 'listing__title', 'actor__email')
    readonly_fields = ('actor', 'action', 'shop', 'listing', 'report', 'notes', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ShopSection)
class ShopSectionAdmin(ModelAdmin):
    list_display = ('name', 'shop', 'position', 'is_visible', 'updated_at')
    list_filter = ('is_visible',)
    search_fields = ('name', 'shop__name')
    raw_id_fields = ('shop',)


@admin.register(ShopSectionItem)
class ShopSectionItemAdmin(ModelAdmin):
    list_display = ('section', 'listing', 'position')
    search_fields = ('section__name', 'listing__title')
    raw_id_fields = ('section', 'listing')


@admin.register(ShopMembership)
class ShopMembershipAdmin(ModelAdmin):
    list_display = ('user', 'shop', 'role', 'status', 'invited_by', 'joined_at', 'revoked_at')
    list_filter = ('role', 'status')
    search_fields = ('user__email', 'shop__name', 'invited_by__email')
    raw_id_fields = ('shop', 'user', 'invited_by')
    readonly_fields = ('joined_at', 'revoked_at')


@admin.register(ShopInvitation)
class ShopInvitationAdmin(ModelAdmin):
    list_display = ('email', 'shop', 'role', 'invited_by', 'created_at', 'expires_at', 'accepted_at', 'revoked_at')
    list_filter = ('role', 'created_at', 'accepted_at', 'revoked_at')
    search_fields = ('email', 'shop__name', 'invited_by__email')
    raw_id_fields = ('shop', 'invited_by', 'accepted_by')
    readonly_fields = ('token_digest', 'created_at', 'accepted_at', 'revoked_at')


@admin.register(ShopAuditEvent)
class ShopAuditEventAdmin(ModelAdmin):
    list_display = ('action', 'shop', 'actor', 'target_type', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('description', 'shop__name', 'actor__email', 'target_id')
    readonly_fields = ('shop', 'actor', 'action', 'target_type', 'target_id', 'description', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
