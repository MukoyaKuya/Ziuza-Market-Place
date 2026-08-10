import uuid

from django.conf import settings
from django.db import models


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='carts',
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(user__isnull=False),
                name='uniq_cart_per_user',
            ),
            models.UniqueConstraint(
                fields=['session_key'],
                condition=models.Q(user__isnull=True) & ~models.Q(session_key=''),
                name='uniq_anon_cart_per_session',
            ),
        ]


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE)
    variant = models.ForeignKey(
        'listings.ListingVariant',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    quantity = models.PositiveIntegerField(default=1)
    personalization_text = models.TextField(blank=True, default='')
    personalization_data = models.JSONField(default=dict, blank=True)
    personalization_signature = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'listing', 'personalization_signature'],
                condition=models.Q(variant__isnull=True),
                name='uniq_cartitem_base_variant',
            ),
            models.UniqueConstraint(
                fields=['cart', 'listing', 'variant', 'personalization_signature'],
                condition=models.Q(variant__isnull=False),
                name='uniq_cartitem_with_variant',
            ),
        ]
