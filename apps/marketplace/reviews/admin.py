from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.marketplace.reviews.models import (
    Review,
    ReviewHelpfulVote,
    ReviewMedia,
    ReviewReminder,
    ReviewReport,
)
from apps.marketplace.reviews.services import moderate_review_report


class ReviewMediaInline(TabularInline):
    model = ReviewMedia
    extra = 0
    readonly_fields = ('original_name', 'content_type', 'size', 'created_at')


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ('listing', 'shop', 'buyer', 'rating', 'is_verified_purchase', 'moderation_status', 'helpful_count', 'created_at')
    list_filter = ('rating', 'is_verified_purchase', 'moderation_status', 'is_visible')
    search_fields = ('title', 'body', 'seller_response', 'listing__title', 'buyer__email', 'shop__name')
    raw_id_fields = ('listing', 'shop', 'buyer', 'order_item', 'seller_responded_by')
    readonly_fields = ('is_verified_purchase', 'helpful_count', 'created_at', 'edited_at', 'seller_responded_at')
    inlines = (ReviewMediaInline,)


@admin.register(ReviewReport)
class ReviewReportAdmin(ModelAdmin):
    list_display = ('review', 'reporter', 'reason', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('review__listing__title', 'reporter__email', 'details', 'moderator_notes')
    raw_id_fields = ('review', 'reporter', 'reviewed_by')
    readonly_fields = ('created_at', 'reviewed_at', 'reviewed_by')
    actions = ('hide_reported_reviews', 'dismiss_reports')

    @admin.action(description='Hide reviews and action selected reports')
    def hide_reported_reviews(self, request, queryset):
        for report in queryset.select_related('review__shop', 'review__buyer', 'review__listing'):
            if report.status == 'open':
                moderate_review_report(actor=request.user, report=report, hide=True, notes='Review hidden after moderator assessment.')

    @admin.action(description='Dismiss selected reports')
    def dismiss_reports(self, request, queryset):
        for report in queryset.select_related('review__shop', 'review__buyer', 'review__listing'):
            if report.status == 'open':
                moderate_review_report(actor=request.user, report=report, hide=False, notes='Report dismissed after moderator assessment.')


@admin.register(ReviewHelpfulVote)
class ReviewHelpfulVoteAdmin(ModelAdmin):
    list_display = ('review', 'user', 'created_at')
    search_fields = ('review__listing__title', 'user__email')
    raw_id_fields = ('review', 'user')


@admin.register(ReviewReminder)
class ReviewReminderAdmin(ModelAdmin):
    list_display = ('order_item', 'sent_at')
    search_fields = ('order_item__order__public_number', 'order_item__title_snapshot')
    raw_id_fields = ('order_item',)
    readonly_fields = ('sent_at',)
