import uuid
from decimal import Decimal

from django.db import models


class ShopDailyMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='daily_metrics',
    )
    date = models.DateField(db_index=True)
    orders = models.PositiveIntegerField(default=0)
    units_sold = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    followers = models.PositiveIntegerField(default=0)
    listing_saves = models.PositiveIntegerField(default=0)
    returning_viewers = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['shop', 'date'], name='uniq_shop_daily_metric'),
        ]
        indexes = [
            models.Index(fields=['shop', 'date'], name='analytics_sday_idx'),
        ]

    def __str__(self):
        return f'{self.shop_id} @ {self.date}'


class ListingDailyMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='listing_daily_metrics',
    )
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_metrics',
    )
    listing_uuid = models.UUIDField(db_index=True)
    title_snapshot = models.CharField(max_length=200)
    date = models.DateField(db_index=True)
    units_sold = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-units_sold']
        constraints = [
            models.UniqueConstraint(
                fields=['shop', 'listing_uuid', 'date'],
                name='uniq_listing_daily_metric',
            ),
        ]
        indexes = [
            models.Index(fields=['shop', 'date'], name='analytics_lday_idx'),
        ]

    def __str__(self):
        return f'{self.title_snapshot} @ {self.date}'
