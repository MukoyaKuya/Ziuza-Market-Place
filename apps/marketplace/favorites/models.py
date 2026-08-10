import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Favorite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'listing')]
        ordering = ['-created_at']


class ListingCollection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listing_collections')
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=240, blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['user', 'name'], name='uniq_user_collection_name')]

    def __str__(self):
        return f'{self.name} — {self.user}'


class CollectionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collection = models.ForeignKey(ListingCollection, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='collection_items')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']
        constraints = [models.UniqueConstraint(fields=['collection', 'listing'], name='uniq_collection_listing')]


class ShopFollow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followed_shops')
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='followers')
    alerts_enabled = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'shop'], name='uniq_user_shop_follow')]


class ListingAlert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listing_alerts')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='alerts')
    price_change_enabled = models.BooleanField(default=True)
    back_in_stock_enabled = models.BooleanField(default=True)
    last_price = models.DecimalField(max_digits=12, decimal_places=2)
    was_in_stock = models.BooleanField(default=False)
    last_checked_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'listing'], name='uniq_user_listing_alert')]
