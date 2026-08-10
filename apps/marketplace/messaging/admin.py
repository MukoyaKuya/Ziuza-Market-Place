from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.marketplace.messaging.models import Conversation, CustomOrderRequest, Message


class MessageInline(TabularInline):
    model = Message
    extra = 0
    raw_id_fields = ('sender',)


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ('shop', 'buyer', 'listing', 'updated_at')
    search_fields = ('shop__name', 'buyer__email', 'listing__title')
    inlines = [MessageInline]
    raw_id_fields = ('shop', 'buyer', 'listing')


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ('conversation', 'sender', 'created_at')
    search_fields = ('sender__email', 'body')
    raw_id_fields = ('conversation', 'sender')


@admin.register(CustomOrderRequest)
class CustomOrderRequestAdmin(ModelAdmin):
    list_display = ('shop', 'buyer', 'listing', 'status', 'budget', 'needed_by', 'created_at')
    list_filter = ('status',)
    search_fields = ('description', 'shop__name', 'buyer__email', 'listing__title')
    raw_id_fields = ('shop', 'buyer', 'listing')
